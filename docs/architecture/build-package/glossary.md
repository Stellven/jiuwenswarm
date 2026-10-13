# Canonical vocabulary and PRD crosswalk

This page owns terminology for maintained architecture prose, tables and diagram labels. The received PRD remains verbatim; its words and clause numbers remain source references. The crosswalk explains responsibilities and relationships rather than declaring unlike components interchangeable. The [coverage map](coverage.md) and [decisions](principles.md#decisions-and-source-amendments) retain actual amendments; vocabulary edits do not change product scope.

## Delivery, implementation and research conventions

| Preferred wording | Scope and convention |
|---|---|
| M1 Delivery Phase 1 - Governed Research Baseline | Contains the fixed research workflow and operational shell, integrated through Implementation Stages 0–7. Short form: Delivery Phase 1. |
| M1 Delivery Phase 2 - Local-Isolated RSI Validation | Contains the required bounded offline RSI path, integrated through Implementation Stage 8. Short form: Delivery Phase 2. |
| M1 Delivery Phase 3 - Dynamic System Integration | Contains applicable advanced compiler, planning, binding, routing, alternate verifier and Code Mode integration efforts. Each receives an evidenced outcome; non-blocking scope does not permit silently skipping it. |
| Implementation Stage 0–8 | Refers to an engineering integration milestone and its runnable exit. Always qualify numbered stages with “Implementation”; source §§6.3–6.11 retain their identifiers. |
| Research step: Ingestion (§3.1), Requirement Compilation (§3.2), etc. | Refers to product research responsibilities in §§3.1–3.9. Use the responsibility name and source clause. PRD “Stage 3.8” points to Scientific Evaluation (§3.8), not Implementation Stage 3 or 8. |
| SwarmFlow runtime phase | Refers to an executing native workflow-script phase; preserve the native identifier `phase`. A delivery phase can contain many runtime phases. |
| M1 Delivery Phase 1 - Intent Compilation and Verification Slice (formerly TRIAL-1) | New maintained display name for the first bounded build. Contains text intake, Intent compiler CC, intent Evaluator Gate, durable evidence and accepted intent or halt. It contributes foundation evidence and Brief preparation; it does not complete Delivery Phase 1, Implementation Stage 1's downstream work consumer, or Implementation Stage 2's Research Brief. Short form: Intent Compilation and Verification Slice. |

Keep “formerly TRIAL-1” adjacent to the first display-name occurrence on each maintained page. Historical references may retain TRIAL-1. This editorial rename does not allocate or rename a TASK, IF, schema, directory or runtime identifier; coding agents register or reconcile those through the live workflow. The existing `immediate-plan.md` path remains stable.

## Components and responsibilities

| PRD or owner wording | Architecture wording | Meaning and reading destination |
|---|---|---|
| Ingestion; Qualified Intake Package (§3.1) | Intake; qualified intake | Capture original text, extract permitted documents, and bind separately supplied assets to a run. [M1 workflow](m1-design.md). |
| Requirement Compilation / Intention Compiler (§3.2, §4.7) | Intent compiler followed by Requirement compiler | Two independently checked responsibilities under D5. Accepted intent contains intermediate extraction; the accepted Research Brief contains the downstream requirements contract. D5 retains two bounded compiler invocations; the external advanced Intention Compiler belongs to Delivery Phase 3 integration. [Intent Compilation and Verification Slice (formerly TRIAL-1)](immediate-plan.md), then [workflow](workflow.md). |
| Research Brief / `Research_Brief.json` | Research Brief | Contains accepted objectives, scope, constraints, preferences, metrics and evidence obligations. Preserve the PRD artifact filename; the intermediate intent contains a narrower extraction. |
| Default DAG; TaskGraph; SwarmFlow (§4.6, §4.8) | Research workflow graph; fixed or dynamic graph; frozen graph | TaskGraph describes plan structure; SwarmFlow executes a workflow. Delivery Phase 1 binds a fixed graph; Delivery Phase 3 may propose a dynamic graph. Freeze records accepted topology, bindings and limits. Scheduler determines readiness; harness supervises execution. These responsibilities are not interchangeable names for the graph. [Workflow](workflow.md). |
| Capability Capsule; `search_capsule.md`, etc. (§4.1) | CC declaration and implementation | A prompt file is one implementation form; it does not replace typed ports, immutable implementation identity, or checks. [Capsules](capsules.md), [declaration](capsule/declaration.md). |
| CC Runner (§4.6, §4.9) | Runner | Shared execution infrastructure for work and verifier CCs. Builder is a work responsibility, not another universal runner. |
| Builder / POC Implementation (§3.6, §4.9) | POC builder CC | Constructs bounded code, harness, dependency declaration, and package; analytical outputs belong to their own CCs. |
| Evaluator Gate (§4.2); verifier gate; architecture “Verifier” | Evaluator Gate | Contains Tier 1 deterministic checks, Tier 2 runtime verifier CC assessment, and protected host decision/durable release. Name a boundary by subject where useful: intent Evaluator Gate, plan Evaluator Gate, aggregate node Evaluator Gate. [Exact boundary](capsules.md#exact-verification-boundary). |
| Verifier Agent; AI Reviewer Agent (§4.3.4); infrastructure `verifier_capsule.md`; gate capsule | Runtime verifier CC; intent verifier CC; plan verifier CC | Supplies read-only semantic assessment in a separate protected context. Assessment feeds the gate host; it does not itself release output. “Gate capsule” in older material refers only to this assessment component. |
| Mandatory deterministic guard / guard profile / binder | Guard check / guard profile / protected binder | A guard contains reusable admitted checking logic or a trusted primitive; a profile contains an independently approved obligation-to-check recipe; the binder assigns these into a frozen contract. [Guard design](guard-design.md). A planner proposes extra checks but cannot approve its own mandatory profile. |
| Scientific evaluator (§3.8); `scientific_evaluator_capsule.md` | Scientific evaluation CC | Interprets admitted measurements against the frozen protocol. Its scientific verdict is data subsequently checked by a runtime verifier. It cannot release itself. |
| Secure Fixture Oracle; independent evaluator/referee (RSI owner §3.Y; master §4.4) | RSI referee and fixture oracle | Protected offline evaluation. Oracle controls hidden fixture access; referee runs fixed scoring and returns only permitted feedback. A runtime verifier is not given hidden fixtures. [Offline RSI](placement.md#offline-rsi). |
| Certification / registry / standing | Admission / library / eligibility | Admission records whether a version is eligible; activation selects an admitted default; suspension revokes eligibility. A scorecard is evidence, not activation authority. |
| Data Foundations / System Memory (§4.5) | Run-state authority plus evidence and derived records | SQLite owns release/lifecycle; files retain raw evidence and exports. Native Task Memory and Coding Memory are reasoning aids. D6/D9 reconcile supplementary capture defaults. [Data design](m1-design.md#data-and-state-ownership). |
| Stage Evidence Bundle | Stage Evidence Bundle | Exact output plus inputs, runtime observations, check context, and attributable references used by the verification boundary. |
| Capsule Run Record; Run Bundle; scorecard | Capsule Run Record; Run Bundle; scorecard | Preserve PRD export meanings. Verifier calls are attributable too; a scorecard cannot erase failed attempts or certify unmeasured reliability. |
| Scientific Benchmarking (§3.7) | Scientific benchmark CC | Baseline then treatment under the user's frozen protocol, inside the research run. |
| Phased System Validation; external benchmark harness | Platform benchmarker | Ordinary headless client comparing platform configurations on matched cases. It does not construct the user's scientific verdict. [Automation](automation.md). |

## Identities, ports, and outcomes

**Use role-qualified names.** Write “intent verifier CC”, “plan verifier CC”, “RSI referee”, “fixture oracle”, or “protected gate host”. Avoid bare “verifier agent” where two paths are possible. A shared verifier implementation may have multiple pinned profiles; profile isolation and evidence scope remain explicit.

| Term | Rule |
|---|---|
| Stage / task / node / attempt | Delivery Phase names baseline/RSI/dynamic integration. Implementation Stage names integration milestones 0–8. A research responsibility is a workflow role; task groups objectives; node represents an objective with a Node Execution Contract; attempt is an execution of that node; invocation identifies each subordinate CC call. A coding TASK and native SwarmFlow runtime phase are separate identities. |
| Declaration name / version / hash | Stable capability name, display version, and exact immutable identity are distinct. Never use a display label as a content pin. |
| Node Execution Contract (§4.1.3–4) | Protected run-specific objective, accepted port bindings, output/check/evidence obligations, exact participating CC pins and effective limits; it may narrow admission but never widen it. [Shapes](contracts-and-native-reuse.md). |
| Product account / local execution identity | Stable product user and durable profile are independent of OS identity/workspace. Local token/OS restrictions authorize the execution host; cloud profile persistence does not authorize remote workflow execution. |
| Artifact type / port / reference | Type names semantic meaning; port names the input/output role; reference identifies stored content. A filesystem path alone does not prove accepted identity or freshness. |
| Freeze / protocol registration | Graph freeze fixes topology and bindings before research execution. Hypothesis registration later fixes experimental criteria before build/measurement. Future output references are not fabricated values. |
| `PASS_WITH_KNOWN_LIMITATIONS` | Advances only if every mandatory condition passed; carry warnings forward. It cannot excuse a failed required boundary. |
| `ENVIRONMENT_BLOCKED` / `BLOCKED` | Detailed runtime verdict / normalized test or display status. Delivery Phase 3 implementation-accounting status has a separate context. Preserve runtime values and reasons; do not replace them with delivery status. `ESCALATE_TO_HUMAN` is an action, not a sixth gate verdict. |
| Scientific `FAIL` or `INCONCLUSIVE` | Hypothesis rejected or evidence between pre-registered bounds. Validly executed scientific evaluation can still receive infrastructure `PASS` and reach Delivery. |
| NOT_RUN / unavailable / stale | No observation, unavailable telemetry, or invalidated evidence. None means zero cost, failed science, or a pass. |

## Naming and schema principles

Use canonical display names throughout maintained prose, headings, tables and diagram labels. Explain what components contain, produce, consume or control; avoid blanket equations between roles or layers. Do not replace PRD bytes, source schema keys, status enums, artifact filenames, native identifiers or historical records. Required CC sources retain their bytes; their internal M1/M2/M3/M4 labels describe source profiles/maturity, not M1 Delivery Phase numbers.

When terminology changes, update labels and rendered diagram views together, retain stable paths where possible, and repair heading fragments. If a replacement changes producer, consumer, authority, budget, verdict or behavior, record a design decision rather than a naming edit.

Use descriptive capability names consistently across declarations, diagrams, task agreements, and records. Existing PRD artifact names remain the translation anchors. Spec Kit owns exact identifier syntax, wire keys, enum serialization, and file layout through versioned agreements; examples in this design do not introduce competing schemas.

Every shared payload has one semantic owner, a version, validation rules, and identified producers/consumers. Distinguish missing, unknown, unavailable, and not applicable. Preserve units, metric direction, evidence origin, warnings, and scope. Content and identity are immutable after acceptance; derived summaries cite their source. Additive fields require explicit compatibility rules rather than assuming all readers tolerate them. Reject unsupported mandatory semantics; do not silently drop them.

Keep reusable capability declaration, Node Execution Contract, invocation binding, runtime observation, verifier assessment, authoritative gate decision, and aggregate score separate. A schema-valid self-assertion is not evidence of execution. Future readers must be able to reconstruct which versions, policy, inputs, and accepted predecessors produced a decision.
