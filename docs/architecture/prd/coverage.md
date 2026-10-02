---
type: index
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../m1/pipeline.md, ../seams.md, ../system/nodes.md, ../system/blackboxes.md]
provides: [architecture.prd_coverage]
consumes: [m1.run_plan, system.seams, system.nodes]
depends_on: [../../product/prd-m1-full-2026-10-01.txt, ../m1/pipeline.md, ../seams.md, ../system/nodes.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
tags: [prd, coverage, ownership, m1]
---

# Full M1 PRD coverage and responsibility map

This is the navigation index from the full M1 PRD to its architecture owners. A row points to the canonical contract or design page; it does not imply that every linked area is complete or approved. `checked` means reviewed against the cited sources; `blackbox` is a usable provisional interface; `draft` still needs its area loop. Muk owns the architecture and Capability Capsule (CC), including the shared schemas and APIs that let these areas connect. Each workstream retains its product semantics and acceptance intent.

## PRD clause to architecture coverage

| PRD clauses | Architecture source of truth | Responsibility / current state |
|---|---|---|
| 1.1–1.5 product goal, phase model, invariants, definition of done | [M1 overview](../m1-architecture.md), [system overview](../system/overview.md), [pipeline](../m1/pipeline.md) | Product invariants are cross-cutting constraints; stage-specific fulfillment is traced below. |
| 1.6 PRD and architecture ownership boundary | [architecture ownership](../architecture.md), [payload types](../types/types.md) | Architecture owns canonical schemas and module connections; workstream owners own domain semantics. |
| 2.1–2.8 domain, input, scientific integrity, autonomy, evidence policies | [full PRD review](prd-m1-full-review.md), [intake](../types/intake.md), [research brief](../types/research-brief.md), [pipeline](../m1/pipeline.md), [seams](../seams.md) | Cross-cutting policies; each consuming module must cite the applicable clause in its area design. |
| 2.9 execution/security boundary | [permissions](../capsule/permissions.md), [runner](../capsule/runner.md), [M1 process boundary](../capsule/process-boundary.md), [open issue](../open-issues.md) 54 | The product requirement is mapped to a provisional generated-code API; general capsule-effect coverage and the concrete security mechanism remain open. |
| 2.10 data/traceability; 2.11 RSI; 2.12 non-goals | [types](../types/types.md), [observability](../system/observability.md), [seams](../seams.md#data-foundation), [seams](../seams.md#rsi), [full PRD review](prd-m1-full-review.md) | Shared records are CC-owned; Data Foundation and RSI integration contracts are cross-workstream seams. |
| 3.0 Codex CLI integration | [integration](../system/integration.md), [toolchain](../capsule/toolchain.md#m01-launcher) | CC integration boundary; cited existing-code claims must be source-verified before code work. |
| 3.1 Ingestion | [intake](../types/intake.md), [launcher](../capsule/toolchain.md#m01-launcher), [open issues](../open-issues.md) 45 | CC owns launcher and intake type; resources/readiness decision 45 affects intake and downstream dataset consumers. |
| 3.2.1–3.2.7 Requirement Compilation | [intent capsule](../m1/intent-capsule.md), [requirement capsule](../m1/requirement-capsule.md), [intent_ir](../types/intent-ir.md), [research_brief](../types/research-brief.md), [brief gate](../m1/brief-gate.md) | CC capsule/schema contract; Brief product meaning follows the full PRD and open issues. |
| 3.3.1–3.3.6 Search & Ideation | [search capsule](../m1/search-capsule.md), [search gate](../m1/search-gate.md), [idea_set](../types/idea-set.md), [search operators](../m1/op-local-search.md) and [scholarly search](../m1/op-scholarly-search.md) | Checked producer interface for Screening. |
| 3.4.1–3.4.7 Screening and selection | [Screening capsule](../m1/screening.md), [screening assessments](../types/screening-assessments.md), [rank helper](../m1/op-rank-opportunities.md), [opportunity card](../types/opportunity-card.md), [gate](../m1/screening-gate.md), [issues 48–53](../open-issues.md) | Muk owns CC/schema/integration; Ramika confirms rubric and domain-filter semantics. Blackbox until owner decisions and seam review. |
| 3.5.1–3.5.5 claims and hypothesis | [hypothesis](../m1/hypothesis.md), [hypothesis blueprint](../types/hypothesis-blueprint.md), [issues 41, 44, 45](../open-issues.md) | Provisional consumer of `opportunity_card`; threshold and intake decisions local to this area. |
| 3.6.1–3.6.5 POC implementation | [POC](../m1/poc.md), [POC bundle](../types/poc-bundle.md), [issues 43, 45](../open-issues.md) | Builder/runtime semantics and CC capsule seam; requires dependency provisioning and input-resource decisions. |
| 3.7.1–3.7.4 scientific benchmarking | [benchmark](../m1/benchmark.md), [benchmark payload](../types/benchmark-payload.md), [M1 process boundary](../capsule/process-boundary.md), [issues 40, 42, 43, 54](../open-issues.md) | Stage capsule and generated program are separate executions; the M1 process boundary is required but provisional, so Benchmark is not ready until it passes review and its pre-check. |
| 3.8.1–3.8.6 scientific evaluation | [evaluation](../m1/evaluation.md), [evaluation verdict](../types/evaluation-verdict.md), [issue 44](../open-issues.md) | Scientific classification is distinct from the gate verdict; classification rule is still proposed. |
| 3.9.1–3.9.4 delivery | [delivery](../m1/delivery.md), [research report](../types/research-report.md), [open issues](../open-issues.md) 36 | Report and deliverable contract; owner confirmation needed for remaining gate/review semantics. |
| 4.1 Capability Capsule | [capsule overview](../capsule/capsule.md), [Declaration](../capsule/fields.md), [authoring](../capsule/authoring.md), [runner](../capsule/runner.md), [toolchain](../capsule/toolchain.md) | Muk / CC owns the shared capability API, schema, invocation, governance and composition contracts. |
| 4.2 Evaluator Gate & Verifier | [gate host](../capsule/gate-host.md), [gate capsule pattern](../capsule/gate-capsules.md), [gate seam](../seams.md#evaluator-gate-and-verifier), [issues 46–47](../open-issues.md) | Ramika owns evaluator criteria and fold policy; Muk/CC owns host, API, and record integration. |
| 4.3 Foundational Models & Routing | [Model Routing seam](../seams.md#model-routing), [routing design](../model-routing/README.md), [routing review](../reviews/2026-10-01-model-routing-review.md) | Model Routing owns routing behavior; CC owns `cc.model` and pinned-capsule integration. |
| 4.4 RSI Integration | [RSI seam](../seams.md#rsi), [RSI capsule contract](../capsule/rsi.md), [fixture oracle](../capsule/fixture-oracle.md), [issues 40, 50, 55–56](../open-issues.md) | M1 requires the offline optimizer and hidden-fixture oracle; Saurav owns optimization behavior, CC owns Candidate/admission and the shared API/record contracts. The [engine/attempt-log contract](../capsule/rsi-engine.md) is drafted; hidden-set policy and verified isolation remain owner blockers. |
| 4.5 Data Foundations | [Data Foundation seam](../seams.md#data-foundation), [run records](../data-foundation/capsule-run-records.md) | Suraj owns Data Foundation's view/export behavior; CC owns canonical records and event sources. |
| 4.6 Harness Core | [system nodes](../system/nodes.md), [pipeline](../m1/pipeline.md), [runner](../capsule/runner.md), [toolchain](../capsule/toolchain.md) | Muk/CC owns static M1 launcher, freeze, call pipeline, runner, and halt contracts; Planner/Phase 2 extends the run plan. |
| 4.7 Intention Compilers | [intent capsule](../m1/intent-capsule.md), [requirement capsule](../m1/requirement-capsule.md), [intent IR](../types/intent-ir.md) | CC owns the current M1 compiling seam; advanced intention compilation remains an external dependency. |
| 4.8 Planner | [node model](../system/nodes.md#locked-nodes-and-planned-nodes), [run plan](../types/run-plan.md), [pipeline](../m1/pipeline.md) | Phase 2 Planner owns plan generation; CC owns the run-plan schema and freeze boundary. |
| 4.9 Builder | [POC](../m1/poc.md), [builder seam](../seams.md) | Builder owns code/asset construction semantics; CC defines capsule, artifact, and restricted-execution connections. |
| 5.1 Visibility/statistics | [observability](../system/observability.md), [integration](../system/integration.md) | CC owns event/API contract; user-facing metrics and telemetry presentation need their owner design. |
| 5.2–5.3 Installer, CLI, web UI | [integration](../system/integration.md), [toolchain](../capsule/toolchain.md), [overview](../system/overview.md) | Entry/runtime surfaces connect to CC; [Workstation](../system/workstation.md) and [environment](../system/environment.md) specify APIs, startup, authentication and doctor; runtime integration remains unbuilt. |
| 5.4 Accounts/security/privacy | [permissions](../capsule/permissions.md), [M1 process boundary](../capsule/process-boundary.md), [fixture oracle](../capsule/fixture-oracle.md), [issues 40, 45, 54](../open-issues.md) | CC owns declared effects and runner permissions; generated-code and hidden-fixture boundaries are separate provisional contracts pending principal/IPC and enforcement design. |
| 5.5 Message channels | [integration](../system/integration.md), [intake](../types/intake.md) | Channel adapters are inputs to the same intake contract; M1 accepts native local CLI/Web/TUI; external channels remain excluded, per [workstation](../system/workstation.md). |
| 5.6 System configuration | [integration](../system/integration.md), [launcher](../capsule/toolchain.md#m01-launcher), [issue 47](../open-issues.md) | CC owns configuration consumption at run boundaries; product-specific settings remain owner-defined. |
| 6.1–6.13 implementation stages and handoff boundary | [M1 design order](../m1/order.md), [current module/code/process map](../system/modules.md), [black boxes](../system/blackboxes.md) | Sequencing source is the PRD; this architecture maps contracts and owners, not Spec Kit or implementation tasks. |

## Workstream ownership and contract boundary

| Workstream | Product/design owner | Architecture / shared-contract owner | Canonical seam pages |
|---|---|---|---|
| M1 architecture and Capability Capsule | Muk | Muk | [architecture](../architecture.md), [CC capsule](../capsule/capsule.md), [types](../types/types.md), [system diagram](../system/diagram.md) |
| Requirement, Search, Screening, and research-stage behavior | Ramika owns product readings/rubrics where specified; Muk owns CC integration and canonical schemas | Muk for schemas/APIs; stage owner for semantics and acceptance criteria | [pipeline](../m1/pipeline.md), stage capsule/gate pages, [open issues](../open-issues.md) |
| Evaluator/Verifier | Ramika | Muk for CC gate host/API/records | [gate host](../capsule/gate-host.md), [seam](../seams.md#evaluator-gate-and-verifier) |
| Model Routing | Model Routing workstream | Muk for `cc.model`, pinned calls and records | [routing seam](../seams.md#model-routing), [routing design](../model-routing/README.md) |
| RSI | Saurav | Muk for CC capsule, admission, and mutation-boundary contracts | [RSI seam](../seams.md#rsi), [RSI contract](../capsule/rsi.md) |
| Data Foundation | Suraj | Muk for canonical records/events; Suraj for its derived views/exports | [Data Foundation seam](../seams.md#data-foundation), [run records](../data-foundation/capsule-run-records.md) |
| Planner / Phase 2 | Phase 2 track | Muk for run-plan schema and freeze API | [node model](../system/nodes.md), [run plan](../types/run-plan.md) |
| Builder and generated-code execution | Builder/runtime owners; Xiaoyang and Muk for containment mechanism | Muk for CC declared effects and capsule-call boundary; CC owns the provisional generated-process API | [permissions](../capsule/permissions.md), [process boundary](../capsule/process-boundary.md), [issues 40, 42, 43, 54](../open-issues.md) |
| Entry, UI, installation, accounts and message channels | Owning workstation/product track; must be confirmed as each area is opened | Muk for adapters and intake/run APIs | [integration](../system/integration.md), [intake](../types/intake.md) |

## Coverage rule

Every new area adds its exact PRD subclauses to its front matter and to the relevant row above, names one owner page for each shared type/API, and lists every producer, consumer, gate, and control-flow dependency. A clause without a page or a recorded reason is uncovered. A change to a shared contract reopens every dependent page listed by the owning page and [the architecture process](../PROCESS.md). This map is intentionally `draft`: areas marked provisional or merely linked have not passed their own source-verified review and seam canary.

## Cross-cutting handoff coverage

| PRD clauses / coder questions | Contract owner | Remaining acceptance boundary |
|---|---|---|
| 3.0, 4.1, 4.3, 4.6, 6.13; ownership/reuse/process/calls | [modules](../system/modules.md), [integration](../system/integration.md), [lifecycle](../system/lifecycle.md) | Native adapters need runtime integration; public APIs replace private coupling |
| 4.2.8–4.2.9, 4.6.1–4.6.4; commit/release/halt/restart | [Verification](../schemas/verification-record.md), [Gate](../capsule/gate-host.md), [system records](../system/records.md) | Save failure never authorizes a successor; preserved evidence and human review own restart |
| 3.1.2, 3.5.5, 3.7.3, 4.5.1–4.5.4; files/evidence/frozen data | [storage](../system/storage.md), [measurement protocol](../m1/measurement-protocol.md), [Data Foundation seam](../seams.md#data-foundation) | Lossless required capture separate from optional projections; missing registered methods block their experiment |
| 2.9, 4.1.4, 4.4.9, 5.4.3; isolation/credentials/network/IPC | [environment](../system/environment.md), [process boundary](../capsule/process-boundary.md), [oracle](../capsule/fixture-oracle.md) | Source conflict 40, wheelhouse43, profiles57; no fallback to unconfined execution |
| 5.1–5.6; local installation/config/CLI/Web/TUI/tmux/artifacts | [workstation](../system/workstation.md), [environment](../system/environment.md) | Native view/entry integration25–26 remains runtime acceptance; external messaging and distributed modes excluded |
| 4.4.1–4.4.9; offline attempts/Candidate/activation | [RSI engine](../capsule/rsi-engine.md), [system records](../system/records.md) | Saurav resolves hidden final/loop scheduling55; no live mutation or automatic activation |
| 3.5–3.9, 4.9; Builder-to-Benchmark-to-Evaluation-to-Report | [full plan](../m1/pipeline.md), [research gates](../m1/research-gates.md), canonical version2 type pages | Owner thresholds/classification41/44 and Screening48–53 stay provisional; static report template source is available |
| 4.2.9, 6.13; separate components and integration/fault hooks | [verification](../system/verification.md) | Invocation points and expected evidence specified; coder supplies commands, tests and actual results |

All linked contracts are drafts/provisional unless their own status explicitly says otherwise. Clause coverage does not claim coding readiness or executed platform acceptance. The Phase 2 experimental track is outside the static M1 acceptance path here; its existing planner seams remain isolated.
