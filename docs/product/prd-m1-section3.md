# M1 System PRD: Section 3, Main Workflow Pipeline (checkpoint)

> **Copied verbatim** from Ramika's Discord post of 2026-09-29, 3:55 PM. The PRD owner is Ramika. The PRD is not finished yet: the vertical features and the per-module PRDs are still to come. This copy is kept for reference only; the owner's version wins.

## Announcement

Hey @everyone 👋

I just wrapped up the Main Workflow Pipeline (Section 3) for the M1 System PRD. Before we all get too deep into our individual component PRDs, I wanted to share the current system architecture so nobody is stuck designing in a black box. The PRD is not finished yet as the vertical features need to be added + your model PRDS but this is a checkpoint of context for you guys in writing your PRDS.

Think of this as the master blueprint. It shows exactly how the Swarmflow DAG executes step-by-step and, more importantly, where all of our individual modules plug in.
A few quick callouts for your specific areas:

Capability Capsules (_capsule.md): You'll see throughout Section 3 how the DAG relies entirely on static files (like search_capsule.md or poc_capsule.md) to restrict agent behavior at every single stage. These capsules act as strict contracts, containing the prompt instructions, allowed tools, and exact JSON schemas. They form a physical boundary that prevents the agents from hallucinating or going out of scope.

Model Routing: Check out Section 3.0. I mapped out how the temporary Codex CLI adapter is structured. Instead of throwing this code away later, we are wrapping it in a clean interface so the dynamic Model Router can inherit it as a permanent "fallback endpoint" to keep the pipeline alive if our main API keys ever fail or hit rate limits.

RSI & Intention Compiler: Because RSI and dynamic routing are complex, the PRD explicitly separates the project into a deterministic "M1 baseline" and a dynamic "Phase 2 test track". This means you are completely unblocked to build your advanced, autonomous features in an offline sandbox without worrying about your experimental code breaking the stable main pipeline.

Verifier (My track): You'll notice every single node ends with a handoff to the 4.2 Evaluator Gate. This gate is the universal tollbooth of the platform. Before data can move from Stage A to Stage B, it must pass this two-tier check (programmatic Python assertions followed by an LLM semantic judge) to ensure no broken code or malformed JSON crashes the system.

Take a look when you can. Let's use this to make sure our individual module designs align with the overarching system handoffs! 🚀

---

## Table of Contents & Implementation Order

> **Note to AI/Codex Agent:** This Table of Contents dictates the exact chronological implementation sequence for Milestone 1 (M1). You must follow this order strictly. Do not attempt to implement downstream workflow nodes (e.g., 3.2) until the preceding dependencies (e.g., 3.0 and 3.1) are fully implemented, refactored, and passing.

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
*   4.6 Harness & Intention Compilers

**5. Vertical Features (The Platform Shell)**
*   5.1 CLI & Webapp / UI
*   5.2 Visibility & Statistics (Telemetry)
*   5.3 Account Management & Permissions
*   5.4 System Configurations (config.yaml)

**6. Component Details & Payload Specs**



### 3.0 Codex CLI Integration (Priority Unblocker)

**Description:** A temporary, high-priority adapter that bridges local JiuwenSwarm execution to our active Codex subscription. This bypasses the need for enterprise API keys and unblocks all downstream pipeline testing. 

#### 3.0.1 Existing Implementation Verification & Refactor
*   **Definition & Expectation:** The agent must inspect the repository for the developer's existing Codex CLI adapter code, verify it correctly intercepts OpenJiuwen's native API calls, and refactor it for stability if necessary.
*   **Whitelist (M1 Scope):**
    *   Intercept native OpenJiuwen model invocation requests (e.g., standard OpenAI-compatible `/v1/chat/completions` calls).
    *   Route intercepted requests through the local active Codex CLI process.
    *   Return parsed responses back to the OpenJiuwen runtime in the standard expected format.
*   **Blacklist (Excluded from M1):**
    *   Building a custom local proxy server from scratch (leverage the existing CLI adapter code).
    *   Handling complex multi-turn conversational streaming (stick to synchronous, single-turn completion requests for the DAG).
*   **Dependencies:**
    *   *Requires Input from:* Any Swarmflow node requesting LLM generation.
    *   *Provides Output to:* The active DAG execution context.

#### 3.0.2 Abstraction for "Endpoint of Last Resort"
*   **Definition & Expectation:** Structures the CLI adapter cleanly so that, rather than being deleted when API keys arrive, it can be handed off to the Model Routing intern to be registered as a permanent fallback pathway.
*   **Whitelist (M1 Scope):**
    *   Wrap the adapter in a standardized Python class/interface that mimics a standard model provider endpoint.
    *   Log adapter timeouts or authentication drops to the local telemetry run-tree.
*   **Blacklist (Excluded from M1):**
    *   Wiring this adapter directly into the dynamic multi-model router on the `main` branch (that integration happens post-M1 when the feature branch merges).
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

#### 3.1.2 User-Supplied Material Import
*   **Definition & Expectation:** Imports reference materials and explicit file references supplied by the user to ground the research.
*   **Whitelist (M1 Scope):**
    *   Read static files placed directly into a designated local workspace directory (e.g., `./workspace/input/`).
    *   Parse raw text exclusively from `.txt`, `.md`, and `.pdf` extensions.
*   **Blacklist (Excluded from M1):**
    *   Live internet scraping (arXiv URLs, PubMed).
    *   Direct GitHub repository cloning.
    *   Complex document chunking/vectorization (handled natively by memory modules later if needed).
    *   Proprietary office formats (`.docx`, `.pptx`).
*   **Dependencies:**
    *   *Requires Input from:* Local filesystem.
    *   *Provides Output to:* 3.1.5 Intake Qualification.

#### 3.1.3 Intake Context Binding
*   **Definition & Expectation:** Binds the intake materials to the authorized user, session, and workspace.
*   **Whitelist (M1 Scope):**
    *   Bind execution to the local single-user system profile defined in `config.yaml`.
    *   Map file ingestion strictly to the active Swarmflow run-ID.
*   **Blacklist (Excluded from M1):**
    *   Multi-tenant enterprise SSO (Single Sign-On) authentication.
    *   Cross-session user state persistence.
*   **Dependencies:**
    *   *Requires Input from:* `jiuwenswarm` runtime environment.

#### 3.1.4 Real-Time Deduplication & Provenance Registration
*   **Definition & Expectation:** Filters malformed content, canonicalizes inputs, and records origin metadata (timestamp, access path) for the run tree.
*   **Whitelist (M1 Scope):**
    *   Programmatic file size limits (e.g., reject files $>50\text{MB}$).
    *   Record local file paths, file sizes, and ingest timestamps into the Swarmflow telemetry log.
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
    *   LLM-based evaluations of whether the prompt makes logical sense (this is deferred to the Stage 1 Evaluator Gate).
*   **Dependencies:**
    *   *Requires Input from:* 3.1.1 Request Capture and 3.1.2 Material Import.
    *   *Provides Output to:* 3.2 Requirement Compilation.



### 3.2 Requirement Compilation

> **External Dependency Flag (Intention Compiler):** The sub-features in this section are currently defined as a static, one-shot baseline to guarantee pipeline execution for M1. This scope is **subject to revision** pending the integration sync with the cross-office intern developing the advanced "Intention Compiler." Any dynamic or interactive behaviors introduced by their module will be scoped into the Phase 2 (Cluster Mode) test track, while this strict one-shot schema remains our Phase 1 default.

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
*   **Blacklist (Excluded from M1):**
    *   Interactive, multi-turn clarification dialogues with the human user (explicitly deferred to Future State / Phase 2 Intention Compiler).

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
*   **Definition & Expectation:** Defines observable success criteria, proof obligations, decision thresholds, and failure conditions.
*   **Whitelist (M1 Scope):**
    *   Define concrete target evaluation metrics (e.g., latency reduction $\ge 20\%$, memory overhead $\le 16\text{GB}$).
*   **Dependencies:**
    *   *Provides Output to:* Stage 3.7 (Benchmarking) to define the pass/fail thresholds.

#### 3.2.7 Requirement Contract Confirmation
*   **Definition & Expectation:** Assembles a versioned contract with executable task semantics and records user confirmation or authorized assumptions.
*   **Whitelist (M1 Phase 1 Scope - Static Baseline):**
    *   Package all extracted fields (Intent, Scope, Constraints, Metrics) into a final standard `Research Brief` JSON payload.
    *   Pass this static JSON file explicitly to the deterministic Swarmflow script to trigger the next DAG node.
*   **Whitelist (M1 Phase 2 Scope - Dynamic Test Track):**
    *   Pass the compiled `Research Brief` contract directly to the JiuwenSwarm Leader Agent to test dynamic intent resolution and autonomous task routing.
*   **Blacklist (Excluded from M1 Entirely):**
    *   Halting the execution to wait for asynchronous human approval before proceeding.
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for verification before passing to Stage 3.3).


### 3.3 Search & Ideation

**Description:** The primary literature retrieval and synthesis node. This stage consumes the structured Research Brief and executes both local and bounded external search queries to generate an initial set of evidence-grounded candidate ideas. All execution logic for these sub-features is defined within the `search_capsule.md` contract.

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
    *   *Requires Input from:* 4.4 Tool & Operator Architecture (`deepsearch` local and API connectors).

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
    *   *Provides Output to:* 4.2 Evaluator Gate (for independent verification of schema and token limits before passing to Stage 3.4 Idea Screening).



### 3.4 Idea Identification / Screening / Opportunity Selection

> **Architectural Distinction (3.3 vs. 3.4):** While Stage 3.3 is **divergent** (broadly exploring the literature to synthesize all scientifically valid possibilities), Stage 3.4 is **convergent and pragmatic**. Its objective is not to generate new concepts or re-verify literature claims, but to ruthlessly evaluate incoming candidates against the user's explicit project constraints (compute budget, technical feasibility, and implementation scope). It prunes non-viable proposals down to a single winning opportunity.

**Description:** The deterministic filtering node of the workstation. This stage ingests the evidence-grounded candidate ideas from Search & Ideation and evaluates them against multi-dimensional expert scoring rubrics adapted from `sciencediscovery/assessment-screening` (measuring feasibility, scientific novelty, and compute alignment). It prunes low-viability proposals and outputs a bounded, ranked portfolio of structured Opportunity Cards for hypothesis formulation. All execution logic is encapsulated within `screening_capsule.md`.

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

#### 3.4.5 Technical Opportunity Screening (Deterministic Rubric)
*   **Definition & Expectation:** Screens novelty, evidence maturity, technical feasibility, compute alignment, and the existence of a credible verification path using ported rubrics from `sciencediscovery/assessment-screening`.
*   **Whitelist (M1 Scope):**
    *   Execute a single-turn LLM evaluation scoring each Idea Card on three 1–5 scales:
        1.  *Novelty:* Difference from baseline approaches cited in the brief.
        2.  *Technical Feasibility:* Plausibility of implementation within standard PyTorch/Python frameworks.
        3.  *Compute Alignment:* Strict compliance with the hardware bounds defined in `Research Brief` (e.g., single GPU).
    *   Require a 1-sentence deterministic justification for each numerical score.
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
    *   Rank all cards and select the Top-1 highest-scoring opportunity card to advance down the deterministic Swarmflow pipeline.
    *   Append rejection/deferral rationales for all lower-ranked candidates into the output metadata.
    *   Package the winning card into `Opportunity_Card.json`.
*   **Blacklist (Excluded from M1):**
    *   Interactive human-in-the-loop idea selection (M1 execution proceeds automatically with the top rubric winner).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for schema and scoring validation prior to handoff to 3.5 Generate Technical Claims & Hypothesis).



### 3.5 Generate Technical Claims & Hypothesis

**Description:** The experimental design node. This stage translates the single winning Opportunity Card from Stage 3.4 into a rigid, testable blueprint. It explicitly defines the dependent/independent variables, expected performance metrics, and success criteria required by the downstream POC Implementation node. All execution logic is encapsulated within `hypothesis_capsule.md`.

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
    *   Define a strict, binary failure condition (e.g., "If VRAM reduction is $<10\%$, the hypothesis is falsified").
    *   Pre-register these thresholds so they are frozen into the JSON contract before any POC code is generated, preventing the system from moving goalposts after preliminary testing.
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

> **Capsule Execution Note:** All sub-features within this stage (3.6.1 through 3.6.5) are executed entirely within the `poc_capsule.md` file. The Swarmflow DAG does not run a separate script or agent for each sub-feature. Instead, `poc_capsule.md` acts as the complete, unified contract for the entire node. It contains the prompt instructions, the permissions for the `CodeSearch` operator, and the strict JSON output schema that forces the agent to sequentially step through environment preparation, code generation, integration, and the mechanical smoke test before outputting the final payload.

**Description:** The execution node. This stage consumes the rigid `Hypothesis_Blueprint.json` generated in Stage 3.5 and translates it into a reproducible proof-of-concept Python script. It acts strictly as an assembly phase: it writes the code, wires the components together, and zips them into an artifact that is benchmark-ready. All execution logic, tool constraints, and output schemas for this stage are strictly encapsulated within `poc_capsule.md`.

#### 3.6.1 POC Implementation Environment Preparation
*   **Definition & Expectation:** Sets up the isolated environment needed for the POC, including dependencies, data paths, runtime constraints, and compute resources.
*   **Whitelist (M1 Scope):**
    *   Map the user-supplied local workspace files (ingested in 3.1) and static validation datasets into a standardized sandboxed directory (`/workspace/poc/`).
    *   Generate a static `requirements.txt` based on the framework requirements detailed in the `Research Brief`.
*   **Blacklist (Excluded from M1):**
    *   Dynamic, autonomous installation of packages via pip during runtime. (M1 assumes the base OpenJiuwen environment or explicitly pre-installed packages).
*   **Dependencies:**
    *   *Requires Input from:* 3.1 Ingestion (Local Workspace Directory).

#### 3.6.2 POC Construction (Code Generation)
*   **Definition & Expectation:** Constructs the code, models, and prompts required to validate the POC.
*   **Whitelist (M1 Scope):**
    *   Invoke the whitelisted `CodeSearch` operator to navigate the local repository, perform syntax-aware chunking, and pinpoint the exact file and line numbers required for the intervention.
    *   Generate a standalone, single-file Python patch script (`poc_patch.py`) that implements the technical mechanism defined in the Hypothesis Blueprint.
*   **Blacklist (Excluded from M1):**
    *   Autonomous multi-file refactoring across a large legacy codebase (M1 restricts generation to bounded, minimal test harnesses).

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
    *   Deploying the containerized runtime prototype to external cloud clusters. (M1 benchmarking occurs strictly within the local Swarmflow execution context).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate (for script bounds checking prior to passing to 3.7 Benchmarking).



### 3.7 Scientific Benchmarking (POC Execution)

> **Architectural Note (The Core User Loop):** This node represents the scientific execution of the user's specific POC script within the Swarmflow DAG. It executes the core value proposition of the platform: *"I have this baseline (uploaded in 3.1), how can I make it better (hypothesized in 3.5 and coded in 3.6), so let's run them side-by-side and compare the results."* This is distinct from the overarching "Phased System Validation" project goal (which measures the AI4Research platform's overall performance). 

**Description:** The empirical validation node. This stage unpacks the `POC_Artifact_Bundle.zip` created in Stage 3.6 and executes the code in a sandboxed runtime environment. It strictly executes the protocol defined in the `Hypothesis_Blueprint.json` to collect metrics on the independent/dependent variables, comparing the baseline against the generated patch. All execution instructions are encapsulated in `benchmark_capsule.md`.

#### 3.7.1 Runtime Provisioning & Artifact Unpacking
*   **Definition & Expectation:** Initializes the secure sandbox and installs the explicit requirements generated during POC assembly.
*   **Whitelist (M1 Scope):**
    *   Unpack `POC_Artifact_Bundle.zip` into the active workspace.
    *   Execute `pip install -r requirements.txt` strictly within the isolated runtime environment.
*   **Blacklist (Excluded from M1):**
    *   Resolving dependency conflicts dynamically. (If the environment fails to build, the run is terminated and sent to human triage to avoid infinite debugging loops).
*   **Dependencies:**
*   *Requires Input from:*3.6.5 Testable POC Artifact Consolidation (POC_Artifact_Bundle.zip)

#### 3.7.2 Delta Execution (Baseline vs. Treatment)
*   **Definition & Expectation:** Runs the actual test script to generate comparative data, ensuring a mathematically fair evaluation.
*   **Whitelist (M1 Scope):**
    *   **The Baseline:** Execute the user's original, unmodified codebase or foundation model (as defined in Stage 3.1 and 3.2).
    *   **The Treatment:** Execute the modified codebase utilizing the `poc_patch.py` script written by the Builder agent in Stage 3.6.
    *   Run the baseline first, followed immediately by the treatment, using the exact same hardware state and random seeds to calculate a mathematically valid delta ($\Delta$).
*   **Blacklist (Excluded from M1):**
    *   Evaluating the patch in isolation without running a live baseline comparison (to prevent static hardware advantages from skewing results).

#### 3.7.3 Empirical Data Collection
*   **Definition & Expectation:** Captures the telemetry, logs, and metric outputs generated by the execution harness using the platform's native memory modules[cite: 2].
*   **Whitelist (M1 Scope):**
    *   Utilize OpenJiuwen's native Task Memory and Coding Memory modules to durably capture standard output (`stdout`), standard error (`stderr`), and system runtime telemetry during execution[cite: 2].
    *   Parse the specific dependent variables defined in 3.5 (e.g., peak allocated VRAM, tokens/sec, accuracy loss) and format them into a structured `empirical_results.json` file.
*   **Blacklist (Excluded from M1):**
    *   Agent-driven interpretation of the data (this node strictly collects the numbers; interpretation is reserved for the Evaluator Gate).

#### 3.7.4 Results Consolidation & Handoff
*   **Definition & Expectation:** Packages the raw empirical data alongside the execution logs for final review, acting purely as a clean data handoff.
*   **Whitelist (M1 Scope):**
    *   Bundle `empirical_results.json`, system standard output (`stdout`), and standard error logs (`stderr`) into a final, highly readable `Benchmark_Payload.json`.
*   **Blacklist (Excluded from M1):**
    *   Applying the falsifiability rules or grading the success of the experiment. (This node strictly acts as a data collector).
*   **Dependencies:**
    *   *Provides Output to:* 4.2 Evaluator Gate. (The Tier-2 Verifier Agent built by the intern team takes this payload, compares it against the 3.5 falsifiability contract, and determines if the technical claim is mathematically validated or rejected).


### 3.8 Scientific Evaluation

> **Capsule Execution & Architectural Role:** All sub-features within this stage (3.8.1 through 3.8.6) are executed entirely within `verifier_capsule.md` (adapted from `sciencediscovery/result-evaluator` and `citation-reviewer`). While the **Evaluator Gate** (Section 4.2) acts as a recurring infrastructure checkpoint between all stages, **Stage 3.8 Scientific Evaluation** is a dedicated workflow stage. It performs the in-depth scientific analysis of the benchmark results against the pre-registered hypothesis and claims before the final research report is synthesized in Delivery.

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
*   **Definition & Expectation:** Tags the hypothesis as pass, fail, inconclusive, or conditionally acceptable, identifying blockers and residual risks.
*   **Whitelist (M1 Scope):**
    *   Assign a standardized classification tag: `PASS`, `FAIL`, `INCONCLUSIVE`, or `CONDITIONALLY_ACCEPTABLE`.
    *   **Scientific vs. Infrastructure Routing Flag:** Explicitly declare that a Scientific `FAIL` (a disproven hypothesis) is a valid, successful research outcome. Unlike an Infrastructure `FAIL` (which triggers a `human_session` halt at the gate), a Scientific `FAIL` must advance directly to Stage 3.9 Delivery so the user receives a report explaining why the idea did not work.
    *   Catalog residual constraints and operational risks (e.g., "Tested on batch size 1 only; behavior on distributed clusters unknown").
*   **Blacklist (Excluded from M1):**
    *   Multi-agent debate or dynamic consensus voting for verdict assignment (enforces a single deterministic classification pass).

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

> **Capsule Execution Note:** Just like the previous nodes, this entire stage is strictly encapsulated within a dedicated capsule: `report_capsule.md` (ported from `sciencediscovery/report-writer`). This guarantees the agent focuses solely on formatting and packaging the final output, without attempting to generate new scientific claims or run more code. 

**Description:** The final synthesis and handoff node. It takes the officially graded scientific data and final verdict from the Evaluator Gate, synthesizes the findings into a standardized markdown report, and packages the entire research lifecycle for the user.

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
    *   Log the completed execution trace to the native `/swarmflows` run-tree monitoring to formally close the Swarmflow lifecycle.
*   **Blacklist (Excluded from M1):**
    *   Sending automated notifications or attachments through external message channels (like Slack, WeChat, or Discord) during the M1 baseline.
