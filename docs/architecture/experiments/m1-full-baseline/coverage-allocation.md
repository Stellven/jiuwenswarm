# Current PRD clause coverage

**Reading level: AI reference.** Every numbered heading in the current verbatim PRD has an architectural responsibility below. A mapping is a reading route, not proof that every bullet is implemented. The source whitelist/blacklist and global invariants still apply. [Design review](coverage.md) checks consequential changes and US01–US20; [decisions](principles.md#decisions-and-source-amendments) identify explicit local exceptions.

Current source: [October 7 PRD](sources/product/prd-m1-current-2026-10-07.txt), 188 numbered headings.

| Exact PRD heading | Architectural responsibility |
|---|---|
| §1.1 Product Overview | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.2 M1 Product Goal | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.3 M1 Delivery Phase Model | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.4 Core Product Invariants | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.5 M1 Definition of Done | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.6 PRD and Architecture Ownership Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.7 Requirement Authority & Conflict Resolution | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.8 M1 Scope Label Convention | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.9 M1 Feature Freeze & Delivery Target | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §1.10 M1 Incremental Change & Canonical Documentation Control | [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md); [coverage.md](coverage.md) |
| §1.11 M1 User Story Traceability | [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md); [coverage.md](coverage.md) |
| §2.1 Purpose | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.2 M1 Domain Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.3 User and Deployment Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.4 Input and External Evidence Policy | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.5 Scientific Integrity Policy | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.6 Capability and Agent Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.7 Workflow Autonomy Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.8 Evaluation and Evidence Policy | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.9 Execution and Security Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.10 Data and Traceability Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.11 RSI Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §2.12 M1 Global Non-Goals | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §3.0 Codex CLI Integration (Priority Unblocker) | [model-routing.md](model-routing.md); [placement.md](placement.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §3.0.1 Existing Implementation Verification & Refactor | [model-routing.md](model-routing.md); [placement.md](placement.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §3.0.2 Abstraction for "Endpoint of Last Resort" | [model-routing.md](model-routing.md); [placement.md](placement.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §3.1 Ingestion | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [artifact-inspection.md](artifact-inspection.md) |
| §3.1.1 Request Capture & Channel Signal Intake | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [artifact-inspection.md](artifact-inspection.md) |
| §3.1.2 User-Supplied Material & Execution Asset Import | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [artifact-inspection.md](artifact-inspection.md) |
| §3.1.3 Intake Context Binding | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [artifact-inspection.md](artifact-inspection.md) |
| §3.1.4 Real-Time Deduplication & Provenance Registration | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [artifact-inspection.md](artifact-inspection.md) |
| §3.1.5 Intake Qualification | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [artifact-inspection.md](artifact-inspection.md) |
| §3.2 Requirement Compilation | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.1 Intent Interpretation | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.2 Context Scoping | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.3 Ambiguity Resolution | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.4 Constraint Resolution | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.5 Requirement Prioritization | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.6 Acceptance Definition | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.2.7 Requirement Contract Confirmation | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §3.3 Search & Ideation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.3.1 Search Strategy Formation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.3.2 Multi-Source Signal Discovery (Hybrid Retrieval) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.3.3 Source Qualification & Technical Signal Extraction | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.3.4 Signal Organization & Trend Analysis | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.3.5 Idea Generation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.3.6 Search Coverage Review & Result Compilation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4 Idea Identification / Screening / Opportunity Selection | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.1 Candidate Consolidation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.2 Idea Identification | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.3 Idea Card Formation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.4 Opportunity Definition | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.5 Technical Opportunity Screening (Fixed-Rubric LLM Evaluation) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.6 Strategic Opportunity Screening | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.4.7 Opportunity Portfolio Prioritization | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.5 Generate Technical Claims & Hypothesis | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.5.1 Research Question & Technical Claim Formation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.5.2 Claim, Evidence, Data & Method Modeling (Benchmark Definition) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.5.3 Hypothesis Pool & Mechanism Formation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.5.4 Falsifiability Screening & Hypothesis Contracting (Anti-Overfitting Contract) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.5.5 Verification-Ready POC Design | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.6 POC Implementation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.6.1 POC Implementation Environment Preparation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.6.2 POC Construction (Code Generation) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.6.3 POC Component Integration & Configuration | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.6.4 POC Functional Readiness Validation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.6.5 Testable POC Artifact Consolidation & Benchmark Handoff | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.7 Scientific Benchmarking (POC Execution) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.7.1 Runtime Provisioning & Artifact Unpacking | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.7.2 Delta Execution (Baseline vs. Treatment) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.7.3 Empirical Data Collection | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.7.4 Results Consolidation & Handoff | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8 Scientific Evaluation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8.1 Evaluation Scope & Evidence Assembly | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8.2 Evidence Completeness & Provenance Review | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8.3 Experimental, Reasoning & External Validity Review | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8.4 Claim & Acceptance-Criteria Comparison | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8.5 Verdict, Blocker & Residual-Risk Classification | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.8.6 Refinement & Follow-Up Recording | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.9 Delivery (Report Generation) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.9.1 Delivery Planning & Evidence Handoff | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.9.2 User-Facing Deliverable Generation | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.9.3 Deliverable, Reusable Asset & Knowledge Packaging | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §3.9.4 Authorized Distribution, Knowledge Transfer & Lifecycle Closure | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §4.1 Capability Capsules | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [reference/README.md](reference/README.md) |
| §4.1.1 Capability Declaration & Assembly | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [reference/README.md](reference/README.md) |
| §4.1.2 Governance, Admission, Versioning & Registry Management | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [reference/README.md](reference/README.md) |
| §4.1.3 Node Capability Binding & Runtime Contract Assembly | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [reference/README.md](reference/README.md) |
| §4.1.4 Invocation & Composition | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [reference/README.md](reference/README.md) |
| §4.1.5 Capability Evolution (RSI Boundaries) | [capsules.md](capsules.md); [capsule/declaration.md](capsule/declaration.md); [reference/README.md](reference/README.md) |
| §4.2 Evaluator Gate & Verifier | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.1 Evaluation Evidence Envelope & Two-Tier Gate Execution | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.2 Contract, Schema & Artifact Conformance Evaluator | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.3 Engineering Correctness & Code Quality Evaluator | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.4 Performance, Cost & Benchmark Evaluator | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.5 Security, Privacy, Compliance & IP Evaluator | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.6 Evidence, Factuality & Scientific Validity Evaluator | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.7 Lifecycle, Parity & Human Review Evaluator | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.8 Verdict Aggregation & Orchestration Gate Policy | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.9 M1 Evaluator Acceptance & Failure-Injection Tests | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.2.10 Future State — Autonomous Multi-Faceted Evaluation via Auto Harness | [guard-design.md](guard-design.md); [capsules.md](capsules.md); [reference/checking.md](reference/checking.md) |
| §4.3 Foundational Models & Routing | [model-routing.md](model-routing.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.3.1 Model Capability Registry | [model-routing.md](model-routing.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.3.2 Model Routing & Selection | [model-routing.md](model-routing.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.3.3 Model Usage Auditing | [model-routing.md](model-routing.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.3.4 AI Reviewer Agent (Routing Integration) | [model-routing.md](model-routing.md); [placement.md](placement.md); [failure-and-human.md](failure-and-human.md) |
| §4.4 RSI (Recursive Self-Improvement) Integration | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.1 Text-Based Artifacts (GEPA / MIProV2 / TextGrad) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.2 Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.3 Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.4 DAG and Agent Organization (AFlow / MCTS / ADAS) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.5 Evaluator, Reward, Contract, and Governance | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.6 Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.7 Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.8 Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment) | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.9 Local-Isolated RSI Sandbox & Hidden-Evaluation Isolation | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.4.10 RSI Security Guardrails & Adversarial Validation | [offline-rsi.md](offline-rsi.md); [reference/other-contracts.md](reference/other-contracts.md); [failure-and-human.md](failure-and-human.md) |
| §4.5 Data Foundations | [artifact-inspection.md](artifact-inspection.md); [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §4.5.1 Persistent Memory & Context Retrieval (Agent Memory) | [artifact-inspection.md](artifact-inspection.md); [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §4.5.2 TaskGraph Persistence & Run Bundles (System Memory) | [artifact-inspection.md](artifact-inspection.md); [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §4.5.3 Contract & Capability Conformance Observability | [artifact-inspection.md](artifact-inspection.md); [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §4.5.4 Sample Run Exports (Scaffolding for RSI Handoff) | [artifact-inspection.md](artifact-inspection.md); [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §4.5.5 Extended Graph Management (Future State Only) | [artifact-inspection.md](artifact-inspection.md); [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md) |
| §4.6 Harness Core | [workflow.md](workflow.md); [failure-and-human.md](failure-and-human.md); [artifact-inspection.md](artifact-inspection.md) |
| §4.6.1 Runtime Control Loop & Run Lifecycle Management | [workflow.md](workflow.md); [failure-and-human.md](failure-and-human.md); [artifact-inspection.md](artifact-inspection.md) |
| §4.6.2 DAG Scheduler & Operator Binding | [workflow.md](workflow.md); [failure-and-human.md](failure-and-human.md); [artifact-inspection.md](artifact-inspection.md) |
| §4.6.3 Main Loop Dispatch & Runtime Supervision | [workflow.md](workflow.md); [failure-and-human.md](failure-and-human.md); [artifact-inspection.md](artifact-inspection.md) |
| §4.6.4 Failure Recovery & Resumability | [workflow.md](workflow.md); [failure-and-human.md](failure-and-human.md); [artifact-inspection.md](artifact-inspection.md) |
| §4.6.5 Distributed Infrastructure & Concurrency (Future State Only) | [workflow.md](workflow.md); [failure-and-human.md](failure-and-human.md); [artifact-inspection.md](artifact-inspection.md) |
| §4.7 Intention Compilers | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §4.7.1 Intent Classification & Compilation Variant Selection | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §4.7.2 Goal, Scope and Context Normalization | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §4.7.3 Ambiguity Resolution & Readiness | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §4.7.4 Constraint Compilation | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §4.7.5 Task Contract & Acceptance Compilation | [intent-design.md](intent-design.md); [reference/intent-and-requirements.md](reference/intent-and-requirements.md); [immediate-plan.md](immediate-plan.md) |
| §4.8 Planner | [workflow.md](workflow.md); [reference/other-contracts.md](reference/other-contracts.md); [phase-details.md](phase-details.md) |
| §4.8.1 Task Contract Decomposition | [workflow.md](workflow.md); [reference/other-contracts.md](reference/other-contracts.md); [phase-details.md](phase-details.md) |
| §4.8.2 TaskGraph Construction | [workflow.md](workflow.md); [reference/other-contracts.md](reference/other-contracts.md); [phase-details.md](phase-details.md) |
| §4.8.3 TaskGraph Validation & Feasibility Analysis | [workflow.md](workflow.md); [reference/other-contracts.md](reference/other-contracts.md); [phase-details.md](phase-details.md) |
| §4.9 Builder | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §4.9.1 Build Contract Interpretation & Preparation (Sub-features 1 & 2) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §4.9.2 Code & Experimental Asset Construction (Sub-features 3, 5, 6, & 7) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §4.9.3 Analytical Deliverable Boundary | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §4.9.4 Prototype Assembly & Build Evidence Generation (Sub-features 9 & 12) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §4.9.5 Excluded Capabilities & Advanced Lifecycle Features (Sub-features 4, 10, 11, & 14) | [research-design.md](research-design.md); [reference/other-contracts.md](reference/other-contracts.md); [placement.md](placement.md) |
| §5.1 Visibility & Statistics (Telemetry) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.1.1 Workflow & Platform Status Visibility | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.1.2 Execution Trace Search & Inspection | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.1.3 Resource Usage, Cost & Capacity Management | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.1.4 Runtime Status Visibility | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.2 Installer & CLI & Webapp | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.2.1 CLI Installation & Workstation Initialization (MacOS & Linux - Sub-features 3 & 4) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.2.2 Web Application & Status Service (Sub-feature 5) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.2.3 Native Desktop Applications (Windows & MacOS - Sub-features 1 & 2) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.3 UI | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.3.1 Command-Line Interface (CLI) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.3.2 Web Graphical User Interface (GUI) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.3.3 Terminal User Interface (TUI) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.4 Account Management & Local Security Controls | [placement.md](placement.md); [artifact-inspection.md](artifact-inspection.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.1 Account Registration & User Profile Management (Sub-features 1 & 3) | [placement.md](placement.md); [artifact-inspection.md](artifact-inspection.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.2 Authentication & Local Web Security (Sub-feature 2) | [placement.md](placement.md); [artifact-inspection.md](artifact-inspection.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.3 Runtime Sandboxing & Process Isolation (Security Boundary) | [placement.md](placement.md); [artifact-inspection.md](artifact-inspection.md); [failure-and-human.md](failure-and-human.md) |
| §5.4.4 Privacy & Personal Data Controls (Sub-feature 4) | [placement.md](placement.md); [artifact-inspection.md](artifact-inspection.md); [failure-and-human.md](failure-and-human.md) |
| §5.5 Message Channels | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.5.1 TMUX Session & Terminal Surface Management (Sub-feature 3) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.5.2 External Messaging Integrations: WeChat & Discord (Sub-features 1 & 2) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.6 System Configurations (`config.yaml`) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.6.1 LLM Configuration (Sub-feature 1) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.6.2 User Settings (Sub-feature 2) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.6.3 Cost & Budget Settings (Sub-feature 3) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.6.4 Cluster Settings (Sub-feature 4) | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §5.6.5 Development & Evaluation Run Configuration | [research-design.md](research-design.md); [artifact-inspection.md](artifact-inspection.md); [automation.md](automation.md) |
| §6.1 Purpose | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.2 Implementation Principle | [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md); [coverage.md](coverage.md) |
| §6.2.1 M1 Validation & Verification Governance | [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md); [coverage.md](coverage.md) |
| §6.2.2 Incremental Change Implementation Protocol | [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md); [coverage.md](coverage.md) |
| §6.3 Implementation Stage 0 — Runtime Unblocker & Local Configuration | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.4 Implementation Stage 1 — Core Governed Execution Backbone | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.5 Implementation Stage 2 — Intake, Requirement Contract & Static DAG | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.6 Implementation Stage 3 — Evidence-to-Hypothesis Research Path | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.7 Implementation Stage 4 — Builder & POC Assembly | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.8 Implementation Stage 5 — Benchmarking & Scientific Evaluation | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.9 Implementation Stage 6 — Delivery & End-to-End Research Run | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.10 Implementation Stage 7 — Operational Shell & Workstation Integration | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.11 Implementation Stage 8 — Local-Isolated RSI Integration | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.12 M1 Delivery Phase 3 — Dynamic System Integration | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.13 Architecture Handoff Boundary | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
| §6.14 M1 Implementation Completion & Core Demo Rule | [principles.md](principles.md); [delivery-phases.md](delivery-phases.md); [phase-details.md](phase-details.md) |
