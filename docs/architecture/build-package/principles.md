# Principles and decisions

## Design intent

Preserve the user's research objective. Make evidence and failure reasons inspectable. Bound agent autonomy through declared capabilities, scoped execution, independent verification, and durable gate control. Reuse native components when they satisfy those responsibilities.

The architecture should prevent an agent from omitting a critical feature while believing it followed the design. It should not prescribe private classes, temporary payload schemas, or a test catalog simply to appear complete. The [requirement labels](README.md#intent-and-reading-boundary) distinguish current behavior, future compatibility, and research directions.

## Decisions and source amendments

The following decisions implement the authorized October 6 direction. They are refreshed against the latest supplied PRD. Superseded interpretations are recorded explicitly below rather than treated as unchanged product compliance. Received source files remain unchanged. Other PRD domain restrictions and product obligations still apply.

| ID | Decision and reason | Source disposition |
|---|---|---|
| D1 | Keep an operational static Delivery Phase 1 graph; use direct admitted CC binding into a checked frozen graph for expected Delivery Phase 3 dynamic integration. | Latest §§1.3/2.7/6.5/6.12 supersede the earlier baseline-dynamic exception. Static fallback is executable, not just a fixture; shared runner/contracts/gates; no live restructuring. |
| D2 | Every work invocation has deterministic checks followed by a verifier CC and a protected gate. Pin the checking assignment; never trust producer self-certification. | Retain PRD 1.4 and 4.2. Replace the October 5 optional-verifier path. Verification assessments terminate without recursive semantic checking. |
| D3 | Gate assessments may be CC work; protected host code owns release. Freeze referee assets against RSI. | Retain PRD 2.11, 4.1.5, 4.2.8, 4.4.5 and independent evidence custody. |
| D4 | Default to zero automatic repair/replay and halt new dispatch after a blocking result. Failures remain evidence. | Retain PRD 1.4, 4.6.4; replace October 5 bounded-correction default. Future repair needs a separate decision. |
| D5 | Separate checked intent from checked Research Brief. Preserve material uncertainty; first trial ends at intent. | Explicitly amend the literal one-generation compiler default in §§3.2/4.7 to two bounded compiler invocations within one non-interactive entry. Freeze combined budgets; preserve defaults/Brief/no solution design. This is a product-visible call-budget difference, not silent compliance. Advanced interaction belongs to Delivery Phase 3. |
| D6 | Keep one Docker application service, Python, TypeScript, SQLite run authority, and artifact files. Distinguish application packaging from POC confinement. | Retain local security in 5.4; amend container-deferral assumptions in 4.1.4 and persistence realization in supplementary Data Foundation and master 4.5.2/5.1.2. Amend container/native-only packaging assumptions in 5.2.1–2 and 5.4.3 while retaining local execution authentication, loopback, protected IPC and restricted POC requirements. Stable product identity/profile storage is separate and may be cloud-backed; local-only identity interpretation is superseded. |
| D7 | Preserve the authored CC field list and meaning; let Spec Kit define serialization and active enforcement. Metadata does not promise executable support. | Retain PRD 4.1.1 contracts, pins, and mutation boundaries. Reconcile existing schema/prose version differences explicitly. |
| D8 | Offline RSI remains required Delivery Phase 2. Define its interfaces before planner completion; first trial excludes its execution. | Retain PRD 1.3, 1.5, 4.4, 6.11; replace blanket RSI deferral in the October 5 architecture. |
| D9 | Required release evidence fails closed; optional diagnostics may be unavailable. | Master PRD 1.4, 4.2, 4.5, 6.4 takes precedence over best-effort capture wording in the supplementary data source. |
| D10 | The Evaluator Gate boundary uses deterministic checks and a runtime verifier CC assessment; protected infrastructure interprets the assessment and owns the authoritative decision/release. Verifier capsules are CCs; gates are not. Halt creates correlated human triage; interactive modes use native interaction, headless never waits. Human correction starts a new linked run. | Clarify 4.2, 4.3.4, 4.6.4, 5.3.1–3; preserves verdicts, gate authority and no automatic retry. Intent Compilation and Verification Slice (formerly TRIAL-1) web attention uses native interaction; terminal triage remains full M1. |
| D11 | Platform benchmarker is an optional ordinary client of the one workflow service, using frozen approved evaluation profiles and scoped exports. | Realize 5.3.1, 5.6.5 and the user-required Compose benchmark path. No distributed workers, hidden-fixture access or mandatory-control bypass in product runs. |

| D12 | Stable product identity and durable profiles are separate from one local execution host and workspace lifetime. | Align §§1.1/2.3/5.4; cloud profile persistence permitted, no mandatory cloud provider or remote control. §3.1.3 local profile means execution configuration. |
| D13 | Node objective, Node Execution Contract and CC invocation are separate. Multi-CC nodes retain per-call checks and aggregate node acceptance. | Align §§1.4/4.1/4.2; restrict each CC independently, never pool permissions; bind all evidence to contract and pins. |
| D14 | Account for all delivery phases, stages 0–8 and applicable Delivery Phase 3 outcomes. | Align §§1.3/6.12/6.14; §4.8 already assigns dynamic planning to Delivery Phase 3; keep preliminary Leader checks distinct from protected plan acceptance. Protected independent plan gate outranks Leader self-check. |

| D15 | Reuse admitted guard implementations and independently approved profiles through one protected binder for fixed preparation and planned work. Review exact output against accepted obligations with minimal scoped evidence; enforce disclosure and effects before execution. | Clarify §§1.4/4.1/4.2/5.4 under D2/D3/D9. Retain every mandatory tier, independent policy ownership and durable host release; no self-approved checks or verifier-as-author. |

D12 preserves the new product/execution identity split; D13 preserves node/CC/contract distinction; D14 accounts for all three delivery phases and separates preliminary proposal checking from protected plan acceptance. These are alignment decisions, not additional feature scope.

Task specifications must cite these amendments alongside original clauses. Do not claim unchanged PRD compliance for amended behavior. The [coding entry](handoff.md) owns complete source disposition and coding-task allocation.

The current working source is the [latest received PRD](sources/product/prd-m1-current-2026-10-06.txt). Its §1.7 authority and §6.14 completion rules apply. D1 is now phase-aligned; D5/D6 remain explicit user-authorized realization/amendments. [Source resolutions](delivery-phases.md#source-corrections-and-boundaries) explain interpretation and ownership boundaries without editing received bytes. Intent Compilation and Verification Slice retains a distinct identity; historical M1-001 records cover the Codex adapter; the coding owner registers current identities under the live workflow.

## What remains required

**Required now.** Retain scientific-research scope, supplied baseline and validation resources, bounded permitted academic retrieval, one selected opportunity and hypothesis, pre-registered immutable experiment criteria, restricted generated-code execution, baseline/treatment comparison, and delivery of valid negative findings. Preserve all workflow responsibilities in the [inventory](README.md#complete-capability-inventory).

Complete M1 also includes attributable model calls, time/call limits, run bundles, conformance and scorecard views, exports, local security/configuration, supported native workstation surfaces, and independent offline RSI validation. The first intent pair does not waive these obligations. Alternate model routes remain isolated from the baseline; no model training, distributed deployment, external publication, or automatic candidate activation is introduced.

**Required compatibility.** Preserve composite declarations, pinned dependency closure, verification coverage, lineage, and effect/lifecycle meaning. **Expected M1 Delivery Phase 3:** advanced compiler, Agent Team/Cluster planning, dynamic binding, heterogeneous routing, alternate verifier and applicable Code Mode. **Future direction:** fusion, interaction-screening MCTS, mid-run installation/compensation, multiple planning epochs and remote workers. Do not implement these solely because a field can represent them.

## Architecture and Spec Kit

The overview owns the breadth-first human review route and module readiness meanings. Review responsibility, connections, authority and extension intent here; deepen only where a consequential ambiguity remains. The PRD travels alongside the design. Detailed native records expand this last whole-system design layer for implementation rather than requiring humans to review every generated detail.

Architecture owns intent, major responsibilities, trust boundaries, placement, critical connections, the required CC fields, and the decisions above. Spec Kit owns detailed interfaces, formats, algorithms, prompts, fixture design, development acceptance criteria, tests, and build order under the [live constitution](../../../.specify/memory/constitution.md).

Do not confuse development acceptance criteria with runtime scientific criteria. Experimental success/falsification boundaries belong to the accepted protocol before execution; coding agents cannot revise them in response to results. Separate verifier characterization from a claim of truth or statistical independence.

Follow [TASKS → TASK → one feature directory](handoff.md). Cross-module agreements have one owning TASK; consumers reference it. Register exact clauses and global constraints, then let coding agents decompose work and generate spec/plan/tasks. Use project overrides and direct native commands; vendor workflow approval steps do not add gates to this coding process. Runtime research gates and human RSI activation are product requirements, not coding-review gates.

## Review and evidence

This revision uses source reconciliation, local native-code inspection, an end-to-end walkthrough and explicit disposition of the user-supplied Luna review. Findings are resolved in these pages and the slice design; no coding-review gate is added. [Coverage and SWOT](coverage.md) state what was reviewed and what remains unverified. Earlier review statements are historical, not proof of this revision.

Implementation must later produce block, connected-boundary, and integrated-system evidence. Record the actual candidate, configuration, fixtures, observed failures, unavailable measurements, and verifier limitations in native Spec Kit artifacts. Documentation checks and agent agreement establish neither runtime correctness nor scientific quality.
