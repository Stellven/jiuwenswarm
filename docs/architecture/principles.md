# Principles and decisions

## Design intent

Preserve the user's research objective. Make evidence and failure reasons inspectable. Bound agent autonomy through declared capabilities, scoped execution, independent verification, and durable gate control. Reuse native components when they satisfy those responsibilities.

The architecture should prevent an agent from omitting a critical feature while believing it followed the design. It should not prescribe private classes, temporary payload schemas, or a test catalog simply to appear complete. The three [requirement labels](README.md#intent-and-reading-boundary) distinguish current behavior, future compatibility, and research directions.

## Decisions and source amendments

The following decisions implement the authorized October 6 direction. They supersede conflicting October 5 architecture defaults and the listed frozen PRD assumptions. Received source files remain unchanged. Other PRD domain restrictions and product obligations still apply.

| ID | Decision and reason | Source disposition |
|---|---|---|
| D1 | Select admitted CCs directly into a typed, verified, frozen graph. One execution representation is easier to inspect; defer a separate logical-operator layer. | Amend static-only planning/selection in PRD 1.3, 2.7, 2.12, 4.1.3, 4.8, 6.5. Retain the fixed graph as an evaluation reference; no live restructuring. |
| D2 | Every work invocation has deterministic checks followed by a verifier CC and a protected gate. Pin the checking assignment; never trust producer self-certification. | Retain PRD 1.4 and 4.2. Replace the October 5 optional-verifier path. Verification assessments terminate without recursive semantic checking. |
| D3 | Gate assessments may be CC work; protected host code owns release. Freeze referee assets against RSI. | Retain PRD 2.11, 4.1.5, 4.2.8, 4.4.5 and independent evidence custody. |
| D4 | Default to zero automatic repair/replay and halt new dispatch after a blocking result. Failures remain evidence. | Retain PRD 1.4, 4.6.4; replace October 5 bounded-correction default. Future repair needs a separate decision. |
| D5 | Separate accepted intent from the Research Brief. Preserve material uncertainty rather than silently inventing constraints. First build ends at intent. | Amend one-shot/default compilation assumptions in 3.2 and 4.7 where they conflict. Keep the downstream Research Brief responsibility. No interactive compiler is required by the first trial. |
| D6 | Keep one Docker application service, Python, TypeScript, SQLite run authority, and artifact files. Distinguish application packaging from POC confinement. | Retain local security in 5.4; amend container-deferral assumptions in 4.1.4 and persistence realization in supplementary Data Foundation. |
| D7 | Preserve the authored CC field list and meaning; let Spec Kit define serialization and active enforcement. Metadata does not promise executable support. | Retain PRD 4.1.1 contracts, pins, and mutation boundaries. Reconcile existing schema/prose version differences explicitly. |
| D8 | Offline RSI remains a required separate M1 track. Define its interfaces before planner completion; first trial excludes its execution. | Retain PRD 1.3, 1.5, 4.4, 6.11; replace blanket RSI deferral in the October 5 architecture. |
| D9 | Required release evidence fails closed; optional diagnostics may be unavailable. | Master PRD 1.4, 4.2, 4.5, 6.4 takes precedence over best-effort capture wording in the supplementary data source. |

Task specifications must cite these amendments alongside original clauses. Do not claim unchanged PRD compliance for amended behavior. The [M1 register](../tasks/M1/TASKS.md) owns complete source disposition and coding-task allocation.

## What remains required

**Required now.** Retain scientific-research scope, supplied baseline and validation resources, bounded permitted academic retrieval, one selected opportunity and hypothesis, pre-registered immutable experiment criteria, restricted generated-code execution, baseline/treatment comparison, and delivery of valid negative findings. Preserve all workflow responsibilities in the [inventory](README.md#complete-capability-inventory).

Complete M1 also includes attributable model calls, time/call limits, run bundles, conformance and scorecard views, exports, local security/configuration, supported native workstation surfaces, and independent offline RSI validation. The first intent pair does not waive these obligations. Alternate model routes remain isolated from the baseline; no model training, distributed deployment, external publication, or automatic candidate activation is introduced.

**Required compatibility.** Preserve composite declarations, pinned dependency closure, verification coverage, lineage, and effect/lifecycle meaning. **Future direction:** fusion, interaction-screening MCTS, mid-run installation and compensation, multiple planning epochs, richer routing, and distributed execution. Do not implement these solely because a field can represent them.

## Architecture and Spec Kit

Architecture owns intent, major responsibilities, trust boundaries, placement, critical connections, the required CC fields, and the decisions above. Spec Kit owns detailed interfaces, formats, algorithms, prompts, fixture design, development acceptance criteria, tests, and build order under the [constitution](../../.specify/memory/constitution.md).

Do not confuse development acceptance criteria with runtime scientific criteria. Experimental success/falsification boundaries belong to the accepted protocol before execution; coding agents cannot revise them in response to results. Separate verifier characterization from a claim of truth or statistical independence.

Follow [TASKS → TASK → one feature directory](../code/code_sop/SPEC_KIT_WORKFLOW.md). Cross-module agreements have one owning TASK; consumers reference it. Register exact clauses and global constraints, then let coding agents decompose work and generate spec/plan/tasks. Use project overrides and direct native commands; vendor workflow approval steps do not add gates to this coding process. Runtime research gates and human RSI activation are product requirements, not coding-review gates.

## Review and evidence

The architecture review uses source reconciliation, an end-to-end walkthrough, Luna technical attacks, and a separate presentation attack. Findings are resolved in these pages and the register, not another implementation checklist. Supporting sources are the [historical architecture](old/README.md), [capsule source notes](old/a3aa887be/docs/architecture/prd/capability-capsule-design-notes.md), and cited research on the relevant pages.

Implementation must later produce block, connected-boundary, and integrated-system evidence. Record the actual candidate, configuration, fixtures, observed failures, unavailable measurements, and verifier limitations in native Spec Kit artifacts. Documentation checks and agent agreement establish neither runtime correctness nor scientific quality.
