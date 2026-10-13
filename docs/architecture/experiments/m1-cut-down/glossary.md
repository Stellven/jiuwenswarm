# Canonical vocabulary and PRD crosswalk

This page owns the short PRD-to-architecture responsibility crosswalk and terminology for maintained prose and diagram labels. The received PRD remains verbatim; its words and clause numbers remain source references. The crosswalk explains responsibilities and relationships rather than declaring unlike components interchangeable. The [coverage map](coverage.md) and [decisions](principles.md#decisions-and-source-amendments) retain actual amendments; vocabulary edits do not change product scope.

## Package naming

**Design-package** and **build-package** are interchangeable names for this single maintained architecture package. Keep `docs/architecture/build-package/` as the canonical path; no duplicate folder or separate authority is implied.

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

Read each row as **a PRD responsibility elaborated into cooperating parts**, with an output and an authority boundary. It is a reading map, not a list of aliases or a new allocation of coding TASKs. Use PRD feature names for headings; qualify internal roles by what they do.

| PRD responsibility | Architecture elaboration | Result / authority and detail |
|---|---|---|
| Ingestion (§3.1) | Capture original input; qualify/extract permitted documents; bind supplied project/data assets. | Qualified Intake Package with attribution. Intake infrastructure owns qualification. [Research responsibilities](research-design.md#research-path-and-ports). |
| Requirement Compilation; Intention Compilers (§3.2, §4.7) | Intent compiler CC extracts meaning; its gate accepts intermediate intent; Requirement compiler CC constructs the Brief; its gate checks the Brief. | Accepted `Research_Brief.json` supports planning. D5 deliberately separates the two bounded invocations; advanced compiler integration belongs to Delivery Phase 3. [Workflow](workflow.md). |
| Planner; Harness Core (§4.8, §4.6) | Fixed graph in Delivery Phase 1, planner proposal in Delivery Phase 3; protected binder assigns admitted CCs/checks; plan gate and freeze pin contracts; scheduler and runner dispatch accepted work. | Frozen TaskGraph and run-specific Node Execution Contracts. Planner proposes; protected infrastructure authorizes. SwarmFlow executes the workflow. [Workflow](workflow.md). |
| Search & Ideation; Idea Screening (§3.3–3.4) | Permitted retrieval and cited candidate generation; feasibility/scoring and Top-1 selection; pure ranking helper also serves offline RSI. | Cited ideas, selected opportunity and rejection reasons, checked by their gates. [Research responsibilities](research-design.md#research-path-and-ports). |
| Hypothesis Generation (§3.5) | Form one claim; bind baseline/data/metrics; pre-register success, falsification and inconclusive criteria. | Frozen experimental protocol before building or measuring. [Research responsibilities](research-design.md#research-path-and-ports). |
| POC Implementation; Builder (§3.6, §4.9) | POC builder CC constructs bounded intervention, harness and declared dependencies; readiness checks inspect the package. | Build evidence and POC package; runner executes CCs, while scientific execution belongs to Benchmarking. [Research responsibilities](research-design.md#research-path-and-ports). |
| Scientific Benchmarking (§3.7) | Provision pinned dependencies under isolation; run baseline then treatment under the frozen protocol; retain measurements and raw logs. | Attributable empirical evidence for Scientific Evaluation. [Placement](placement.md). |
| Scientific Evaluation (§3.8) | Scientific evaluation CC applies pre-registered criteria to accepted measurements; runtime verifier checks the resulting assessment. | Scientific conclusion is data; the Evaluator Gate owns infrastructure advancement. A valid negative or inconclusive result can advance. [Research responsibilities](m1-design.md). |
| Delivery / Report Generation (§3.9) | Delivery CC assembles report, artifacts and limitations; its gate checks them; infrastructure transfers accepted output and closes lifecycle. | Traceable report and supporting exports, including valid negative science. [Research responsibilities](m1-design.md). |
| Capability Capsule (§4.1) | Reusable declaration and implementation; immutable dependency pins; admission/library eligibility; per-invocation binding and observations. | A CC may serve a workflow node; the node's contract binds objectives and authority. Prompt files alone do not define the full CC. [Declaration](capsule/declaration.md). |
| Evaluator Gate & Verifier (§4.2) | Tier 1 deterministic guard checks; Tier 2 read-only runtime verifier CC; protected gate host decision and durable release. Guard profiles assign obligations independently of the producer. | Gate host alone authorizes accepted output. Verifier supplies semantic assessment; scientific evaluator and RSI referee have separate roles. [Boundary](capsules.md#exact-verification-boundary), [guards](guard-design.md). |
| Foundational Models & Routing; Codex CLI (§4.3, §3.0) | Protected model bridge and role/profile records; static baseline selection; bounded alternative routing and verifier integration in Delivery Phase 3. | Audited effective model access within frozen limits. [Placement](placement.md), [phase accounting](delivery-phases.md). |
| RSI Integration (§4.4) | Bounded improver proposes candidates; fixture oracle controls hidden evidence; RSI referee scores under fixed rules; library records eligibility; human activation selects an admitted version. | Offline candidate lineage and evaluation evidence; no automatic live promotion. [Offline RSI](offline-rsi.md). |
| Data Foundations (§4.5) | Run-state authority owns lifecycle/release; immutable files retain raw evidence; derived records/exports cite sources; native memory supports reasoning. | Stage Evidence Bundle, Capsule Run Record, Run Bundle and scorecards retain distinct meanings. A scorecard grants no release authority. [Data ownership](research-design.md#data-and-state-ownership). |
| Platform Shell (§5.1–5.6) | Telemetry and status; installer/startup and CLI/Web/TUI; user/profile and local security; terminal surfaces; bounded configuration and budgets. | Operable user-scoped product with authorized local execution. Cloud profile state supplies no remote execution permission. [M1 shell](m1-design.md), [placement](placement.md). |
| System validation (§5.6.5, §6) | Platform benchmarker drives the ordinary headless workflow, compares matched configurations and reads scoped exports. | Platform evidence; the user's Scientific Benchmarking CC supplies research measurements. [Automation](automation.md). |

## Identities, ports, and outcomes

**Use role-qualified names.** Write “intent verifier CC”, “plan verifier CC”, “RSI referee”, “fixture oracle”, or “protected gate host”. Avoid bare “verifier agent” where two paths are possible. A shared verifier implementation may have multiple pinned profiles; profile isolation and evidence scope remain explicit.

| Term | Rule |
|---|---|
| Stage / task / node / attempt | Delivery Phase names baseline/RSI/dynamic integration. Implementation Stage names integration milestones 0–8. A research responsibility is a workflow role; task groups objectives; node represents an objective with a Node Execution Contract; attempt is an execution of that node; invocation identifies each subordinate CC call. A coding TASK and native SwarmFlow runtime phase are separate identities. |
| Declaration name / version / hash | Stable capability name, display version, and exact immutable identity are distinct. Never use a display label as a content pin. |
| Node Execution Contract (§4.1.3–4) | Protected run-specific objective, accepted port bindings, output/check/evidence obligations, exact participating CC pins and effective limits; it may narrow admission but never widen it. [Fields](reference/other-contracts.md#planning-and-node-contracts). |
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

Use descriptive capability names consistently across declarations, diagrams, task agreements, and records. Existing PRD artifact names remain the translation anchors. [Reference contracts](reference/README.md) own shared field names and critical serialization. Internal identifiers/storage layout are implementation choices; examples illustrate the same contracts.

Every shared payload has one semantic owner, a version, validation rules, and identified producers/consumers. Distinguish missing, unknown, unavailable, and not applicable. Preserve units, metric direction, evidence origin, warnings, and scope. Content and identity are immutable after acceptance; derived summaries cite their source. Additive fields require explicit compatibility rules rather than assuming all readers tolerate them. Reject unsupported mandatory semantics; do not silently drop them.

Keep reusable capability declaration, Node Execution Contract, invocation binding, runtime observation, verifier assessment, authoritative gate decision, and aggregate score separate. A schema-valid self-assertion is not evidence of execution. Future readers must be able to reconstruct which versions, policy, inputs, and accepted predecessors produced a decision.

## Composition notation

`V ⊆ C` means a runtime verifier is a capability capsule; `G ∩ C = ∅` means a protected gate is infrastructure, not a capsule. A dependency arrow carries captured/accepted data through governed runtime; it never grants direct bypass of checking. A composite pins member declarations and preserves each member's checks, effects and trace. Effective authority is the intersection of admission, node contract and run policy for each participating CC, never the union of another CC's permissions. See [capsules](capsules.md) for invocation and [field reference](capsule/declaration.md) for declarations.
