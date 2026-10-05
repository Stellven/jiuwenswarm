---
type: index
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, coverage.md]
provides: [architecture.clause_inventory]
consumes: []
depends_on: [coverage.md]
tags: [prd, coverage]
---

# Exact frozen PRD heading inventory

Generated from the frozen October 2 PRD numbered headings. Source line numbers refer to the unchanged [master file](../../product/prd-m1-full-2026-10-02.txt). The group names point to [coverage](coverage.md), which links canonical designs. Whitelist/blacklist items beneath each heading remain binding; a heading's presence here is navigation evidence, not acceptance proof.

| Clause | Exact source heading | Source line | Coverage group |
|---|---|---|---|
| 1 | Overview & M1 Objectives | 40 | 1 |
| 1.1 | Product Overview | 42 | 1 |
| 1.2 | M1 Product Goal | 55 | 1 |
| 1.3 | M1 Phase Model | 75 | 1 |
| 1.4 | Core Product Invariants | 126 | 1 |
| 1.5 | M1 Definition of Done | 174 | 1 |
| 1.6 | PRD and Architecture Ownership Boundary | 193 | 1 |
| 2 | Domain Policy & Restrictions | 220 | 2 |
| 2.1 | Purpose | 222 | 2 |
| 2.2 | M1 Domain Boundary | 229 | 2 |
| 2.3 | User and Deployment Boundary | 248 | 2 |
| 2.4 | Input and External Evidence Policy | 264 | 2 |
| 2.5 | Scientific Integrity Policy | 283 | 2 |
| 2.6 | Capability and Agent Boundary | 313 | 2 |
| 2.7 | Workflow Autonomy Boundary | 329 | 2 |
| 2.8 | Evaluation and Evidence Policy | 346 | 2 |
| 2.9 | Execution and Security Boundary | 362 | 2 |
| 2.10 | Data and Traceability Boundary | 378 | 2 |
| 2.11 | RSI Boundary | 389 | 2 |
| 2.12 | M1 Global Non-Goals | 415 | 2 |
| 3.0 | Codex CLI Integration (Priority Unblocker) | 436 | 3.0 |
| 3.0.1 | Existing Implementation Verification & Refactor | 440 | 3.0 |
| 3.0.2 | Abstraction for "Endpoint of Last Resort" | 454 | 3.0 |
| 3.1 | Ingestion | 466 | 3.1 |
| 3.1.1 | Request Capture & Channel Signal Intake | 470 | 3.1 |
| 3.1.2 | User-Supplied Material & Execution Asset Import | 482 | 3.1 |
| 3.1.3 | Intake Context Binding | 505 | 3.1 |
| 3.1.4 | Real-Time Deduplication & Provenance Registration | 516 | 3.1 |
| 3.1.5 | Intake Qualification | 527 | 3.1 |
| 3.2 | Requirement Compilation | 541 | 3.2 |
| 3.2.1 | Intent Interpretation | 547 | 3.2 |
| 3.2.2 | Context Scoping | 556 | 3.2 |
| 3.2.3 | Ambiguity Resolution | 565 | 3.2 |
| 3.2.4 | Constraint Resolution | 572 | 3.2 |
| 3.2.5 | Requirement Prioritization | 579 | 3.2 |
| 3.2.6 | Acceptance Definition | 584 | 3.2 |
| 3.2.7 | Requirement Contract Confirmation | 591 | 3.2 |
| 3.3 | Search & Ideation | 604 | 3.3 |
| 3.3.1 | Search Strategy Formation | 608 | 3.3 |
| 3.3.2 | Multi-Source Signal Discovery (Hybrid Retrieval) | 617 | 3.3 |
| 3.3.3 | Source Qualification & Technical Signal Extraction | 629 | 3.3 |
| 3.3.4 | Signal Organization & Trend Analysis | 636 | 3.3 |
| 3.3.5 | Idea Generation | 643 | 3.3 |
| 3.3.6 | Search Coverage Review & Result Compilation | 651 | 3.3 |
| 3.4 | Idea Identification / Screening / Opportunity Selection | 662 | 3.4 |
| 3.4.1 | Candidate Consolidation | 668 | 3.4 |
| 3.4.2 | Idea Identification | 678 | 3.4 |
| 3.4.3 | Idea Card Formation | 685 | 3.4 |
| 3.4.4 | Opportunity Definition | 692 | 3.4 |
| 3.4.5 | Technical Opportunity Screening (Fixed-Rubric LLM Evaluation) | 699 | 3.4 |
| 3.4.6 | Strategic Opportunity Screening | 711 | 3.4 |
| 3.4.7 | Opportunity Portfolio Prioritization | 718 | 3.4 |
| 3.5 | Generate Technical Claims & Hypothesis | 732 | 3.5 |
| 3.5.1 | Research Question & Technical Claim Formation | 736 | 3.5 |
| 3.5.2 | Claim, Evidence, Data & Method Modeling (Benchmark Definition) | 745 | 3.5 |
| 3.5.3 | Hypothesis Pool & Mechanism Formation | 754 | 3.5 |
| 3.5.4 | Falsifiability Screening & Hypothesis Contracting (Anti-Overfitting Contract) | 761 | 3.5 |
| 3.5.5 | Verification-Ready POC Design | 769 | 3.5 |
| 3.6 | POC Implementation | 780 | 3.6 |
| 3.6.1 | POC Implementation Environment Preparation | 786 | 3.6 |
| 3.6.2 | POC Construction (Code Generation) | 796 | 3.6 |
| 3.6.3 | POC Component Integration & Configuration | 805 | 3.6 |
| 3.6.4 | POC Functional Readiness Validation | 812 | 3.6 |
| 3.6.5 | Testable POC Artifact Consolidation & Benchmark Handoff | 820 | 3.6 |
| 3.7 | Scientific Benchmarking (POC Execution) | 832 | 3.7 |
| 3.7.1 | Runtime Provisioning & Artifact Unpacking | 838 | 3.7 |
| 3.7.2 | Delta Execution (Baseline vs. Treatment) | 849 | 3.7 |
| 3.7.3 | Empirical Data Collection | 858 | 3.7 |
| 3.7.4 | Results Consolidation & Handoff | 867 | 3.7 |
| 3.8 | Scientific Evaluation | 879 | 3.8 |
| 3.8.1 | Evaluation Scope & Evidence Assembly | 885 | 3.8 |
| 3.8.2 | Evidence Completeness & Provenance Review | 894 | 3.8 |
| 3.8.3 | Experimental, Reasoning & External Validity Review | 902 | 3.8 |
| 3.8.4 | Claim & Acceptance-Criteria Comparison | 909 | 3.8 |
| 3.8.5 | Verdict, Blocker & Residual-Risk Classification | 916 | 3.8 |
| 3.8.6 | Refinement & Follow-Up Recording | 925 | 3.8 |
| 3.9 | Delivery (Report Generation) | 935 | 3.9 |
| 3.9.1 | Delivery Planning & Evidence Handoff | 941 | 3.9 |
| 3.9.2 | User-Facing Deliverable Generation | 949 | 3.9 |
| 3.9.3 | Deliverable, Reusable Asset & Knowledge Packaging | 957 | 3.9 |
| 3.9.4 | Authorized Distribution, Knowledge Transfer & Lifecycle Closure | 964 | 3.9 |
| 4 | Foundation Features (The Engine) | 977 | 4 |
| 4.1 | Capability Capsule | 979 | 4.1 |
| 4.1.1 | Capsule Definition & Assembly | 987 | 4.1 |
| 4.1.2 | Governance, Certification & Registry Management | 998 | 4.1 |
| 4.1.3 | Capability Discovery & Selection | 1010 | 4.1 |
| 4.1.4 | Invocation & Composition | 1020 | 4.1 |
| 4.1.5 | Capability Evolution (RSI Boundaries) | 1031 | 4.1 |
| 4.2 | Evaluator Gate & Verifier | 1052 | 4.2 |
| 4.2.1 | Evaluation Evidence Envelope & Two-Tier Gate Execution | 1061 | 4.2 |
| 4.2.2 | Contract, Schema & Artifact Conformance Evaluator | 1101 | 4.2 |
| 4.2.3 | Engineering Correctness & Code Quality Evaluator | 1130 | 4.2 |
| 4.2.4 | Performance, Cost & Benchmark Evaluator | 1161 | 4.2 |
| 4.2.5 | Security, Privacy, Compliance & IP Evaluator | 1194 | 4.2 |
| 4.2.6 | Evidence, Factuality & Scientific Validity Evaluator | 1229 | 4.2 |
| 4.2.7 | Lifecycle, Parity & Human Review Evaluator | 1260 | 4.2 |
| 4.2.8 | Verdict Aggregation & Orchestration Gate Policy | 1288 | 4.2 |
| 4.2.9 | M1 Evaluator Acceptance & Failure-Injection Tests | 1374 | 4.2 |
| 4.2.10 | Future State — Autonomous Multi-Faceted Evaluation via Auto Harness | 1445 | 4.2 |
| 4.3 | Foundational Models & Routing | 1469 | 4.3 |
| 4.3.1 | Model Capability Registry | 1475 | 4.3 |
| 4.3.2 | Model Routing & Selection | 1488 | 4.3 |
| 4.3.3 | Model Usage Auditing | 1502 | 4.3 |
| 4.3.4 | AI Reviewer Agent (Routing Integration) | 1522 | 4.3 |
| 4.4 | RSI (Recursive Self-Improvement) Integration | 1540 | 4.4 |
| 4.4.1 | Text-Based Artifacts (GEPA / MIProV2 / TextGrad) | 1551 | 4.4 |
| 4.4.2 | Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL) | 1572 | 4.4 |
| 4.4.3 | Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS) | 1580 | 4.4 |
| 4.4.4 | DAG and Agent Organization (AFlow / MCTS / ADAS) | 1602 | 4.4 |
| 4.4.5 | Evaluator, Reward, Contract, and Governance | 1610 | 4.4 |
| 4.4.6 | Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training) | 1630 | 4.4 |
| 4.4.7 | Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL) | 1638 | 4.4 |
| 4.4.8 | Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment) | 1656 | 4.4 |
| 4.4.9 | Offline Sandbox & Hidden-Evaluation Isolation | 1678 | 4.4 |
| 4.4.10 | RSI Security Guardrails & Adversarial Validation | 1704 | 4.4 |
| 4.5 | Data Foundations | 1737 | 4.5 |
| 4.5.1 | Persistent Memory & Context Retrieval (Agent Memory) | 1741 | 4.5 |
| 4.5.2 | TaskGraph Persistence & Run Bundles (System Memory) | 1748 | 4.5 |
| 4.5.3 | Contract Conformance & Observability | 1758 | 4.5 |
| 4.5.4 | Sample Run Exports (Scaffolding for RSI Handoff) | 1766 | 4.5 |
| 4.5.5 | Extended Graph Management (Future State Only) | 1774 | 4.5 |
| 4.6 | Harness Core | 1787 | 4.6 |
| 4.6.1 | Runtime Control Loop & Run Lifecycle Management | 1791 | 4.6 |
| 4.6.2 | DAG Scheduler & Operator Binding | 1799 | 4.6 |
| 4.6.3 | Main Loop Dispatch & Runtime Supervision | 1809 | 4.6 |
| 4.6.4 | Failure Recovery & Resumability | 1818 | 4.6 |
| 4.6.5 | Distributed Infrastructure & Concurrency (Future State Only) | 1827 | 4.6 |
| 4.7 | Intention Compilers | 1837 | 4.7 |
| 4.7.1 | Intent Classification & Compilation Variant Selection | 1847 | 4.7 |
| 4.7.2 | Goal, Scope and Context Normalization | 1857 | 4.7 |
| 4.7.3 | Ambiguity Resolution & Readiness | 1867 | 4.7 |
| 4.7.4 | Constraint Compilation | 1877 | 4.7 |
| 4.7.5 | Task Contract & Acceptance Compilation | 1887 | 4.7 |
| 4.8 | Planner | 1900 | 4.8 |
| 4.8.1 | Task Contract Decomposition | 1904 | 4.8 |
| 4.8.2 | TaskGraph Construction | 1913 | 4.8 |
| 4.8.3 | TaskGraph Validation & Feasibility Analysis | 1923 | 4.8 |
| 4.9 | Builder | 1934 | 4.9 |
| 4.9.1 | Build Contract Interpretation & Preparation (Sub-features 1 & 2) | 1941 | 4.9 |
| 4.9.2 | Code & Experimental Asset Construction (Sub-features 3, 5, 6, & 7) | 1951 | 4.9 |
| 4.9.3 | Analytical Deliverable Boundary | 1962 | 4.9 |
| 4.9.4 | Prototype Assembly & Build Evidence Generation (Sub-features 9 & 12) | 1976 | 4.9 |
| 4.9.5 | Excluded Capabilities & Advanced Lifecycle Features (Sub-features 4, 10, 11, & 14) | 1984 | 4.9 |
| 5 | Vertical Features (The Platform Shell) | 2000 | 5 |
| 5.1 | Visibility & Statistics (Telemetry) | 2005 | 5.1 |
| 5.1.1 | Workflow & Platform Status Visibility | 2009 | 5.1 |
| 5.1.2 | Execution Trace Search & Inspection | 2017 | 5.1 |
| 5.1.3 | Resource Usage, Cost & Capacity Management | 2025 | 5.1 |
| 5.1.4 | Runtime Status Visibility | 2034 | 5.1 |
| 5.2 | Installer & CLI & Webapp | 2045 | 5.2 |
| 5.2.1 | CLI Installation & Workstation Initialization (MacOS & Linux - Sub-features 3 & 4) | 2049 | 5.2 |
| 5.2.2 | Web Application & Status Service (Sub-feature 5) | 2067 | 5.2 |
| 5.2.3 | Native Desktop Applications (Windows & MacOS - Sub-features 1 & 2) | 2076 | 5.2 |
| 5.3 | UI | 2085 | 5.3 |
| 5.3.1 | Command-Line Interface (CLI) | 2089 | 5.3 |
| 5.3.2 | Web Graphical User Interface (GUI) | 2099 | 5.3 |
| 5.3.3 | Terminal User Interface (TUI) | 2110 | 5.3 |
| 5.4 | Account Management & Local Security Controls | 2120 | 5.4 |
| 5.4.1 | Account Registration & User Profile Management (Sub-features 1 & 3) | 2127 | 5.4 |
| 5.4.2 | Authentication & Local Web Security (Sub-feature 2) | 2136 | 5.4 |
| 5.4.3 | Runtime Sandboxing & Process Isolation (Security Boundary) | 2144 | 5.4 |
| 5.4.4 | Privacy & Personal Data Controls (Sub-feature 4) | 2153 | 5.4 |
| 5.5 | Message Channels | 2163 | 5.5 |
| 5.5.1 | TMUX Session & Terminal Surface Management (Sub-feature 3) | 2170 | 5.5 |
| 5.5.2 | External Messaging Integrations: WeChat & Discord (Sub-features 1 & 2) | 2178 | 5.5 |
| 5.6 | System Configurations (`config.yaml`) | 2188 | 5.6 |
| 5.6.1 | LLM Configuration (Sub-feature 1) | 2195 | 5.6 |
| 5.6.2 | User Settings (Sub-feature 2) | 2204 | 5.6 |
| 5.6.3 | Cost & Budget Settings (Sub-feature 3) | 2212 | 5.6 |
| 5.6.4 | Cluster Settings (Sub-feature 4) | 2220 | 5.6 |
| 5.6.5 | Development & Evaluation Run Configuration | 2228 | 5.6 |
| 6 | M1 Implementation Order & Integration Plan | 2247 | 6 |
| 6.1 | Purpose | 2249 | 6 |
| 6.2 | Implementation Principle | 2264 | 6 |
| 6.3 | Implementation Stage 0 — Runtime Unblocker & Local Configuration | 2280 | 6 |
| 6.4 | Implementation Stage 1 — Core Governed Execution Backbone | 2299 | 6 |
| 6.5 | Implementation Stage 2 — Intake, Requirement Contract & Static DAG | 2334 | 6 |
| 6.6 | Implementation Stage 3 — Evidence-to-Hypothesis Research Path | 2354 | 6 |
| 6.7 | Implementation Stage 4 — Builder & POC Assembly | 2376 | 6 |
| 6.8 | Implementation Stage 5 — Benchmarking & Scientific Evaluation | 2398 | 6 |
| 6.9 | Implementation Stage 6 — Delivery & End-to-End Research Run | 2427 | 6 |
| 6.10 | Implementation Stage 7 — Operational Shell & Workstation Integration | 2445 | 6 |
| 6.11 | Implementation Stage 8 — Offline RSI Integration | 2466 | 6 |
| 6.12 | Implementation Stage 9 — Phase 2 Test Tracks | 2490 | 6 |
| 6.13 | Architecture Handoff Boundary | 2509 | 6 |
