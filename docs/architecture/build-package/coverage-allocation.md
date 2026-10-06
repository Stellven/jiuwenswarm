# Current PRD source allocation

Reading map for all 184 numbered feature clauses in the [latest PRD](sources/product/prd-m1-current-2026-10-06.txt). Top-level sections and global restrictions apply across the design. Read exact source bullets and exclusions; a mapped heading is neither an acceptance criterion nor implementation evidence.

[Decisions D1–D15](principles.md#decisions-and-source-amendments) record adopted amendments. [Delivery phases](delivery-phases.md) distinguishes required Delivery Phase 1 baseline, required Delivery Phase 2 RSI, expected Delivery Phase 3 effort/outcome accounting, and the narrower Intent Compilation and Verification Slice (formerly TRIAL-1) slice. Coding agents allocate concrete ACs and interface owners in native records; this table does not duplicate their register.

| PRD clause / exact heading | Architecture responsibility |
|---|---|
| §1.1 Product Overview | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.2 M1 Product Goal | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.3 M1 Delivery Phase Model | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.4 Core Product Invariants | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.5 M1 Definition of Done | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.6 PRD and Architecture Ownership Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.7 Requirement Authority & Conflict Resolution | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.8 M1 Scope Label Convention | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §1.9 M1 Feature Freeze & Delivery Target | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.1 Purpose | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.2 M1 Domain Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.3 User and Deployment Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.4 Input and External Evidence Policy | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.5 Scientific Integrity Policy | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.6 Capability and Agent Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.7 Workflow Autonomy Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.8 Evaluation and Evidence Policy | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.9 Execution and Security Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.10 Data and Traceability Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.11 RSI Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §2.12 M1 Global Non-Goals | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §3.0 Codex CLI Integration (Priority Unblocker) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.0.1 Existing Implementation Verification & Refactor | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.0.2 Abstraction for "Endpoint of Last Resort" | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.1 Ingestion | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.1.1 Request Capture & Channel Signal Intake | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.1.2 User-Supplied Material & Execution Asset Import | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.1.3 Intake Context Binding | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.1.4 Real-Time Deduplication & Provenance Registration | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.1.5 Intake Qualification | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2 Requirement Compilation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.1 Intent Interpretation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.2 Context Scoping | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.3 Ambiguity Resolution | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.4 Constraint Resolution | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.5 Requirement Prioritization | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.6 Acceptance Definition | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.2.7 Requirement Contract Confirmation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3 Search & Ideation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3.1 Search Strategy Formation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3.2 Multi-Source Signal Discovery (Hybrid Retrieval) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3.3 Source Qualification & Technical Signal Extraction | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3.4 Signal Organization & Trend Analysis | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3.5 Idea Generation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.3.6 Search Coverage Review & Result Compilation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4 Idea Identification / Screening / Opportunity Selection | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.1 Candidate Consolidation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.2 Idea Identification | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.3 Idea Card Formation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.4 Opportunity Definition | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.5 Technical Opportunity Screening (Fixed-Rubric LLM Evaluation) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.6 Strategic Opportunity Screening | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.4.7 Opportunity Portfolio Prioritization | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.5 Generate Technical Claims & Hypothesis | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.5.1 Research Question & Technical Claim Formation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.5.2 Claim, Evidence, Data & Method Modeling (Benchmark Definition) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.5.3 Hypothesis Pool & Mechanism Formation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.5.4 Falsifiability Screening & Hypothesis Contracting (Anti-Overfitting Contract) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.5.5 Verification-Ready POC Design | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.6 POC Implementation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.6.1 POC Implementation Environment Preparation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.6.2 POC Construction (Code Generation) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.6.3 POC Component Integration & Configuration | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.6.4 POC Functional Readiness Validation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.6.5 Testable POC Artifact Consolidation & Benchmark Handoff | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.7 Scientific Benchmarking (POC Execution) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.7.1 Runtime Provisioning & Artifact Unpacking | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.7.2 Delta Execution (Baseline vs. Treatment) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.7.3 Empirical Data Collection | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.7.4 Results Consolidation & Handoff | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8 Scientific Evaluation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8.1 Evaluation Scope & Evidence Assembly | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8.2 Evidence Completeness & Provenance Review | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8.3 Experimental, Reasoning & External Validity Review | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8.4 Claim & Acceptance-Criteria Comparison | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8.5 Verdict, Blocker & Residual-Risk Classification | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.8.6 Refinement & Follow-Up Recording | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.9 Delivery (Report Generation) | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.9.1 Delivery Planning & Evidence Handoff | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.9.2 User-Facing Deliverable Generation | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.9.3 Deliverable, Reusable Asset & Knowledge Packaging | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §3.9.4 Authorized Distribution, Knowledge Transfer & Lifecycle Closure | [m1-design.md](m1-design.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [workflow.md](workflow.md) |
| §4.1 Capability Capsules | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.1.1 Capability Declaration & Assembly | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.1.2 Governance, Admission, Versioning & Registry Management | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.1.3 Node Capability Binding & Runtime Contract Assembly | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.1.4 Invocation & Composition | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.1.5 Capability Evolution (RSI Boundaries) | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.2 Evaluator Gate & Verifier | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.1 Evaluation Evidence Envelope & Two-Tier Gate Execution | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.2 Contract, Schema & Artifact Conformance Evaluator | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.3 Engineering Correctness & Code Quality Evaluator | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.4 Performance, Cost & Benchmark Evaluator | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.5 Security, Privacy, Compliance & IP Evaluator | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.6 Evidence, Factuality & Scientific Validity Evaluator | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.7 Lifecycle, Parity & Human Review Evaluator | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.8 Verdict Aggregation & Orchestration Gate Policy | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.9 M1 Evaluator Acceptance & Failure-Injection Tests | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.2.10 Future State — Autonomous Multi-Faceted Evaluation via Auto Harness | [capsules.md](capsules.md); [m1-design.md](m1-design.md); [failure-and-human.md](failure-and-human.md) |
| §4.3 Foundational Models & Routing | [placement.md](placement.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [delivery-phases.md](delivery-phases.md) |
| §4.3.1 Model Capability Registry | [placement.md](placement.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [delivery-phases.md](delivery-phases.md) |
| §4.3.2 Model Routing & Selection | [placement.md](placement.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [delivery-phases.md](delivery-phases.md) |
| §4.3.3 Model Usage Auditing | [placement.md](placement.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [delivery-phases.md](delivery-phases.md) |
| §4.3.4 AI Reviewer Agent (Routing Integration) | [placement.md](placement.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md); [delivery-phases.md](delivery-phases.md) |
| §4.4 RSI (Recursive Self-Improvement) Integration | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.1 Text-Based Artifacts (GEPA / MIProV2 / TextGrad) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.2 Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.3 Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.4 DAG and Agent Organization (AFlow / MCTS / ADAS) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.5 Evaluator, Reward, Contract, and Governance | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.6 Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.7 Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.8 Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment) | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.9 Local-Isolated RSI Sandbox & Hidden-Evaluation Isolation | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.10 RSI Security Guardrails & Adversarial Validation | [offline-rsi.md](offline-rsi.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.5 Data Foundations | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md) |
| §4.5.1 Persistent Memory & Context Retrieval (Agent Memory) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md) |
| §4.5.2 TaskGraph Persistence & Run Bundles (System Memory) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md) |
| §4.5.3 Contract & Capability Conformance Observability | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md) |
| §4.5.4 Sample Run Exports (Scaffolding for RSI Handoff) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md) |
| §4.5.5 Extended Graph Management (Future State Only) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md) |
| §4.6 Harness Core | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.6.1 Runtime Control Loop & Run Lifecycle Management | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.6.2 DAG Scheduler & Operator Binding | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.6.3 Main Loop Dispatch & Runtime Supervision | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.6.4 Failure Recovery & Resumability | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.6.5 Distributed Infrastructure & Concurrency (Future State Only) | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.7 Intention Compilers | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.7.1 Intent Classification & Compilation Variant Selection | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.7.2 Goal, Scope and Context Normalization | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.7.3 Ambiguity Resolution & Readiness | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.7.4 Constraint Compilation | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.7.5 Task Contract & Acceptance Compilation | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.8 Planner | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.8.1 Task Contract Decomposition | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.8.2 TaskGraph Construction | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.8.3 TaskGraph Validation & Feasibility Analysis | [workflow.md](workflow.md); [delivery-phases.md](delivery-phases.md); [contracts-and-native-reuse.md](contracts-and-native-reuse.md) |
| §4.9 Builder | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §4.9.1 Build Contract Interpretation & Preparation (Sub-features 1 & 2) | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §4.9.2 Code & Experimental Asset Construction (Sub-features 3, 5, 6, & 7) | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §4.9.3 Analytical Deliverable Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §4.9.4 Prototype Assembly & Build Evidence Generation (Sub-features 9 & 12) | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §4.9.5 Excluded Capabilities & Advanced Lifecycle Features (Sub-features 4, 10, 11, & 14) | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §5.1 Visibility & Statistics (Telemetry) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.1.1 Workflow & Platform Status Visibility | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.1.2 Execution Trace Search & Inspection | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.1.3 Resource Usage, Cost & Capacity Management | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.1.4 Runtime Status Visibility | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.2 Installer & CLI & Webapp | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.2.1 CLI Installation & Workstation Initialization (MacOS & Linux - Sub-features 3 & 4) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.2.2 Web Application & Status Service (Sub-feature 5) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.2.3 Native Desktop Applications (Windows & MacOS - Sub-features 1 & 2) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.3 UI | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.3.1 Command-Line Interface (CLI) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.3.2 Web Graphical User Interface (GUI) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.3.3 Terminal User Interface (TUI) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.4 Account Management & Local Security Controls | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.1 Account Registration & User Profile Management (Sub-features 1 & 3) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.2 Authentication & Local Web Security (Sub-feature 2) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.3 Runtime Sandboxing & Process Isolation (Security Boundary) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.4 Privacy & Personal Data Controls (Sub-feature 4) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.5 Message Channels | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.5.1 TMUX Session & Terminal Surface Management (Sub-feature 3) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.5.2 External Messaging Integrations: WeChat & Discord (Sub-features 1 & 2) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.6 System Configurations (`config.yaml`) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.6.1 LLM Configuration (Sub-feature 1) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.6.2 User Settings (Sub-feature 2) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.6.3 Cost & Budget Settings (Sub-feature 3) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.6.4 Cluster Settings (Sub-feature 4) | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §5.6.5 Development & Evaluation Run Configuration | [m1-design.md](m1-design.md); [placement.md](placement.md); [automation.md](automation.md); [failure-and-human.md](failure-and-human.md) |
| §6.1 Purpose | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.2 Implementation Principle | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.3 Implementation Stage 0 — Runtime Unblocker & Local Configuration | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.4 Implementation Stage 1 — Core Governed Execution Backbone | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.5 Implementation Stage 2 — Intake, Requirement Contract & Static DAG | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.6 Implementation Stage 3 — Evidence-to-Hypothesis Research Path | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.7 Implementation Stage 4 — Builder & POC Assembly | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.8 Implementation Stage 5 — Benchmarking & Scientific Evaluation | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.9 Implementation Stage 6 — Delivery & End-to-End Research Run | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.10 Implementation Stage 7 — Operational Shell & Workstation Integration | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.11 Implementation Stage 8 — Local-Isolated RSI Integration | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.12 M1 Delivery Phase 3 — Dynamic System Integration | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.13 Architecture Handoff Boundary | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
| §6.14 M1 Implementation Completion & Core Demo Rule | [delivery-phases.md](delivery-phases.md); [coverage.md](coverage.md); [principles.md](principles.md) |
