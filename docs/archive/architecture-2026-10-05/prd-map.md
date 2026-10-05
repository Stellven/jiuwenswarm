---
type: index
status: draft
version: 3
sources: [../product/prd-m1-full-2026-10-02.txt, ../product/SOURCE_FREEZE.md]
provides: [architecture.prd_coverage]
consumes: [arch.flow, system.seams]
depends_on: [flow.md, system/modules.md, system/test-surfaces.md, stories.md, verification.md, runtime.md, rsi.md, placement.md, capabilities/README.md, system/seams.md, build-order.md, decisions.md]
tags: [prd, coverage, ownership, m1]
prd: [1.3, 1.6, 6.2, 6.13]
id: arch.prd_map
level: present
---

# Frozen M1 clause and responsibility coverage

PRD: 1.3, 1.6, 6.2, 6.13

> Answers: Which page covers each frozen M1 PRD clause?

The [source freeze](../product/SOURCE_FREEZE.md) fixes scope. This map is navigation, not executed acceptance. The numbered headings are in the PRD itself ([master PRD](../product/prd-m1-full-2026-10-02.txt)). The source blacklist applies even when a heading contains whitelist items. [Build order](build-order.md#from-these-docs-to-code-and-tasks) covers engineering completeness. Deliberate departures from the PRD are listed in [decisions](decisions.md#prd-deviations) and again below.

## How to read the matrix

Each row maps one source clause to the architecture IDs and pages that carry it, with an allocation status that the task register (TASKS) can copy. Flow IDs (`N_*`, `G_*`) and edges (`A->B`) are from [flow](flow.md). Blocks (`B01`...) are from [modules](system/modules.md). Acceptance rows for each capability are in its page under "Acceptance seeds"; verification rows are in [test surfaces](system/test-surfaces.md#verification-table).

| Status | Meaning |
|---|---|
| Allocated | an owning page and flow node, block or seam exist; the clause can be assigned to a task |
| [PENDING_SOURCE](decisions.md#term-pending-source) | an input from outside architecture is missing (listed in [decisions](decisions.md#pending-source-do-not-invent)); only the affected work is constrained |
| Unallocated | in scope for M1 but no owning page yet; none today |
| Excluded | blacklisted or deferred by the PRD for M1; no design, no task |

## Clause matrix

| Source area | Track | Flow node and edge IDs | Capability or system page (canonical design pages) | Required observation | Allocation status |
|---|---|---|---|---|---|
| 1 product goals and ownership (1.1 to 1.6, incl. definition of done 1.5) | all | all [nodes](system/nodes.md#term-node); `N_node->G_node->N_deliver` for 1.5 items 3 to 10 | [architecture](README.md), [terms](terms.md), [decisions](decisions.md), [tracks](system/experiments.md) | fixed production, required [RSI](rsi.md#term-rsi) and isolated experiments separately identified | Allocated |
| 2 domain, integrity, autonomy, evidence and non-goals | all | `N_intake`, `N_intent`, `G_*`; HALT edges | [Brief](types/research-brief.md), [flow](flow.md), [capabilities](capabilities/README.md), [placement](placement.md), [verification](verification.md), [RSI](rsi.md) | bounded scientific lane and no autonomous repair or unapproved scope | Allocated |
| 3.0 [Model routing](model-routing/README.md#term-model-routing) | production | Model turns under `N_intent`, `N_req`, `N_plan`, `N_node`, `G_*` (B11) | [integration](system/integration.md), [placement](placement.md), [model bridge](system/environment.md#model-bridge) | protected local subscription route and bounded failure | Allocated |
| 3.1 intake | production | `N_intake`; edge `N_intake->N_intent` | [intake](types/intake.md), [extraction](capabilities/extract-text.md), [workstation](system/workstation.md) | permitted local request/assets, deduplication and provenance | Allocated |
| 3.2 requirement compilation | production | `N_intent`, `G_intent`, `N_req`, `G_req`; edges `G_intent->N_req`, `G_req->N_plan` | [intent CC](capabilities/intent-compile.md), [requirement CC](capabilities/requirement-capsule.md), [Brief type](types/research-brief.md), [Brief Gate profile](capabilities/brief-gate.md) | intent derived and accepted first (deviation 2); objective, ambiguities, constraints and acceptance compiled faithfully | Allocated; requirement port wiring for accepted `intent_ir` is PENDING_SOURCE |
| 3.3 search/ideation | production | planned `N_node` + `G_node` (search) | [search](capabilities/search-capsule.md), [ideas](types/idea-set.md), [search Gate](capabilities/search-gate.md) | bounded local/scholarly evidence and referenced candidate ideas | Allocated |
| 3.4 screening | production | planned `N_node` + `G_node` (screening) | [Screening](capabilities/screening.md) (RSI Targets 1 and 2), [ranking](capabilities/op-rank-opportunities.md), [card](types/opportunity-card.md), [Screening Gate](capabilities/screening-gate.md) | fixed dimensions, deterministic selection and rejection evidence | Allocated |
| 3.5 hypothesis | production | planned `N_node` + `G_node` (hypothesis) | [Hypothesis](capabilities/hypothesis.md), [Blueprint](types/hypothesis-blueprint.md), [protocol](capabilities/measurement-protocol.md) | baseline/treatment and scientific rubric pre-registered | Allocated |
| 3.6 POC | production | planned `N_node` + `G_node` (POC) | [POC](capabilities/poc.md), [bundle](types/poc-bundle.md), [workspace](capabilities/op-workspace-io.md) | permitted files and requirements packaged; Builder does not install or perform science | Allocated |
| 3.7 scientific execution | production | planned `N_node` + `G_node` (benchmark) | [benchmark](capabilities/benchmark.md), [payload](types/benchmark-payload.md), [measurement](capabilities/measurement-protocol.md), [process boundary](capsule/process-boundary.md) | one [jiuwenbox](isolation.md#term-jiuwenbox) provision, both arms, trusted samples and raw capture | Allocated; per-platform execution is gated by validation obligations |
| 3.8 scientific evaluation | production | planned `N_node` + `G_node` (evaluation) | [Evaluation](capabilities/evaluation.md), [verdict](types/evaluation-verdict.md), [research Gates](capabilities/research-gates.md) | [frozen](system/lifecycle.md#term-freeze) classification, scientific failure separate from infrastructure failure | Allocated |
| 3.9 report and delivery | production | planned `N_node` + `G_node` (report); `N_deliver` | [report](capabilities/write-report.md), [publication](capabilities/delivery.md), [report type](types/research-report.md), [storage](system/storage.md) | negative/inconclusive science reported; atomic publication and retrieval | Allocated; who renders the report file and POC zip before delivery is undecided |
| 4.1 CC | shared | `N_bind`, `N_run` (library is outside a run) | [terms](terms.md), [Declaration](capsule/fields.md), [tools](capsule/tools.md), [admission](capsule/admission.md), [library](capsule/library.md), [runner](capsule/runner.md) | admitted exact versions and whitelist enforcement separated from future fields | Allocated |
| 4.1.3 dynamic registry discovery and selection on the production path | production | none | read-only catalogue only in [experiments](system/experiments.md) | production names each [capsule](capsule/capsule.md#term-capability-capsule) in the frozen plan; no search or ranking | Excluded for production; Allocated for the isolated catalogue |
| 4.2 [Gate](verification.md#term-gate)/Verifier | shared | `G_intent`, `G_req`, `G_node`; edge `N_node->G_node` | [verification](verification.md), [evidence](types/evidence-bundle.md), [shared verifier](capsule/gate-capsules.md), [Gate host](capsule/gate-host.md), [Verification](schemas/verification-record.md) | [Findings](schemas/finding.md#term-finding) and routing verdicts persisted before release | Allocated; Declaration-derived Gate builder API and profile id rule are PENDING_SOURCE |
| 4.2.10 Auto Harness evaluation | none | none | none | none | Excluded |
| 4.3 models/routing | baseline / isolated | [model bridge](system/model-bridge.md#term-model-bridge) (B11); no flow node selects a capsule | [routing adaptation](model-routing/README.md), [experiments](system/experiments.md), [model client](capsule/runner-broker.md#the-model-client-contract-m05) | endpoint choice never selects a capability; access gating preserved | Allocated; real alternate endpoints PENDING_SOURCE (access approval) |
| 4.4.1 to 4.4.10 RSI, hidden evaluation and adversarial guardrails | required offline | outside the run flow (offline controller B25, oracle B26) | [RSI](rsi.md), [RSI engine](capsule/rsi-engine.md), [oracle](capsule/fixture-oracle.md), [Candidate](schemas/candidate.md), [activation](capsule/library.md) | [RSI target](capsule/rsi.md#term-rsi-target)/mutation limits, private evaluation, violations and manual activation | Allocated |
| 4.4.2, 4.4.4, 4.4.6, 4.4.7, 4.4.8 future-state items (runtime tuning, DAG evolution, product memory learning, weight training, RSI-written [operators](capabilities/README.md#term-operator)) | none | none | none | none | Excluded |
| 4.5 [Observations](schemas/observation.md#term-observation) | shared | capture at every node (B23); records join on `obs_id` | [seam](system/seams.md), [storage](system/storage.md), [records](system/records.md), [benchmark export](system/benchmark-export.md) | lossless required evidence; rebuildable views/export | Allocated |
| 4.5.5 extended graph management | none | none | none | none | Excluded |
| 4.6 Harness | production / shared | `N_dispatch`, `N_run`; edges `G_node->N_dispatch`, `G_node->HALT` | [flow](flow.md), [runtime](runtime.md), [nodes](system/nodes.md), [lifecycle](system/lifecycle.md), [runner](capsule/runner.md) | frozen execution, durable release and explicit restart | Allocated |
| 4.6.5 distributed infrastructure | none | none | none | none | Excluded |
| 4.7 intention | production / isolated | `N_intent`, `G_intent`, `N_req`, `G_req` | [intent CC](capabilities/intent-compile.md), [requirement CC](capabilities/requirement-capsule.md), [experiments](system/experiments.md) | one-shot compilers, no dialogue; experimental dialogue stays pre-dispatch | Allocated; intent repair budget default and nested review caller [Declarations](capsule/fields.md#term-declaration) are PENDING_SOURCE |
| 4.8 planner | production template / isolated | `N_plan`, `N_validate`, `N_bind`; edges `G_req->N_plan->N_validate->N_bind->N_dispatch` | [planner](system/planner.md), [run plan](types/run-plan.md), [freeze](capsule/toolchain.md) | planner proposes once after accepted requirements (deviation 1); first version emits the fixed template; no live mutation/cycles/peer-agent redteam | Allocated; planner entry contract in services schema [family](contracts/principles.md#term-message-family) revision (PENDING_SOURCE) |
| 4.9 Builder | production / isolated | planned `N_node` (POC) | [POC](capabilities/poc.md), [process boundary](capsule/process-boundary.md), [Code Mode](system/experiments.md) | executable synthesis isolated from analytical stages | Allocated |
| 4.9.5 model training, product integration, defect repair loops, deployable services | none | none | none | none | Excluded |
| 5.1 visibility | workstation | Observation of every node | [runtime](runtime.md), [observability](system/observability.md), [workstation](system/workstation.md) | run state, trace, statistics and artifact joins | Allocated; token and cost fields best effort |
| 5.2 installation | workstation | none (startup, outside the flow) | [placement](placement.md), [environment](system/environment.md), [workstation](system/workstation.md) | reproducible install/bootstrap/doctor/startup | Allocated |
| 5.2.3 native desktop applications | none | none | none | none | Excluded |
| 5.3 local interfaces | workstation | `N_intake` entry, run views | [workstation](system/workstation.md), [integration](system/integration.md) | CLI/Web/TUI/tmux share run APIs | Allocated |
| 5.4 accounts/security | shared | none (cross-cutting); Doctor before any run | [environment](system/environment.md), [workstation](system/workstation.md), [oracle](capsule/fixture-oracle.md), [isolation](isolation.md) | local tokens and credentials; generated code cannot read protected material | Allocated |
| 5.5.1 tmux surfaces | workstation | none | [workstation](system/workstation.md) | attach, detach and inspect panes | Allocated |
| 5.5.2 external messaging (WeChat, Discord, Slack, Feishu) | none | none | none | none | Excluded |
| 5.6 configuration/evaluation | shared / isolated | none (frozen configuration read by every node) | [configuration](system/environment.md), [experiments](system/experiments.md), [manifest](system/records.md), [headless export](system/benchmark-export.md) | effective frozen settings; ablation cannot satisfy production acceptance | Allocated |
| 5.6.4 cluster settings | none | none | none | none | Excluded |
| 5.3.1 headless entry and 5.6.5 development/evaluation integration | shared / isolated | `N_intake` (headless), `N_deliver`, export edge | [benchmark export](system/benchmark-export.md), [headless lifecycle](system/lifecycle.md), [experiments](system/experiments.md) | standard invocation and labelled [runs](system/lifecycle.md#term-run); mandatory-control ablations cannot satisfy production acceptance | PENDING_SOURCE for the external benchmark export schema; the adapter is [PENDING_DESIGN](decisions.md#term-pending-design) |
| 6 implementation order | all | all [blocks](system/modules.md#term-block) | [build order](build-order.md), [modules](system/modules.md), [test surfaces](system/test-surfaces.md) | connected slices, full baseline, required RSI, then isolated experiments | Allocated |

## PRD deviations as rows

Each deviation is a recorded decision ([decisions](decisions.md#prd-deviations)). They are accepted, so each row is Allocated. Test them as written here, not as the PRD clause says.

| Deviation | PRD clause | Flow node and edge IDs | Page | Note | Allocation status |
|---|---|---|---|---|---|
| 1 | 2.7, 4.8 hardcoded DAG | `N_plan`, `N_validate`, `N_bind` | [planner](system/planner.md) | planner service emits the DAG once after accepted requirements; validated, bound and frozen before dispatch; M1 emits the fixed template with no model call | Allocated |
| 2 | 3.2, 4.7 intent is Step 2 | `N_intent`, `G_intent` | [intent CC](capabilities/intent-compile.md) | intent CC derives intent first (bounded loop), then one requirement pass; no dialogue | Allocated |
| 3 | 4.2 Gate between stages | `G_intent`, `G_req`, `G_node` | [verification](verification.md) | every dispatch call has a Gate, built from the Declaration; the verifier is a CC with zero RSI mutability | Allocated |
| 4 | 4.1.4, 5.4.3 native process sandbox, containers deferred | none (placement) | [deployment](system/deployment.md), [placement](placement.md) | one Docker container plus inner restricted processes; no per-task containers, no Docker socket | Allocated |
| 5 | 4.4 human activation | none (offline) | [admission](capsule/admission.md) | adds [Puppet admission](capsule/admission.md#term-puppet-admission) for exact hashes (`exempt`); RSI children stay inactive until a human activates | Allocated |
| 6 | 3.2.1, 4.7 single-turn LLM pass | `N_intent` | [intent CC](capabilities/intent-compile.md) | bounded loop: compile, validate, nested review, repair (default 1, cap 4); requirement CC keeps one pass | Allocated |
| 7 | 3.2 one [Brief](types/research-brief.md#term-research-brief) from one compiler | `N_req` | [prep plan](capabilities/prep.plan.json) | one requirement call in the [prep plan](types/run-plan.md#term-prep-plan); a second needs a new decision | Allocated |
| 8 | 4.1.2 strict admission with one `provisional` level | none (library) | [admission](capsule/admission.md), [library](capsule/library.md) | two providers, tested (`provisional`) and Puppet (`exempt`); no `certified` | Allocated |
| 9 | 4.4 RSI targets only Screening | none (offline) | [RSI](rsi.md), [intent CC](capabilities/intent-compile.md) | `research.compile_intent` code and prompts are also RSI-eligible; Gate CCs stay excluded | Allocated |

## Deployment amendment and adjacent proposals

The explicit Docker deployment amendment is traced in [SOURCE_FREEZE](../product/SOURCE_FREEZE.md) and [decisions](decisions.md) (A12, A14, deviation 4). [Deployment](system/deployment.md), [model auth](system/model-auth.md) and [benchmark transport](system/benchmark-export.md) own image, process, credential and endpoint details. These are architecture choices with implementation [checks](capsule/fields.md#term-check), not claims that source files were rewritten or runtime mechanisms were tested.

The [Verifier model-selection proposal](../product/verifier-model-selection-proposal-2026-10-02.md) permits isolated recommendation and unmodified-model integration after access approval. Training, quality claims from functional examples and production-route replacement are excluded. It consumes the existing semantic-assessment contract and cannot change Gate authority.

Each source heading maps to a row here; its whitelist/blacklist and expected observation are checked during source review. A row is not proof that every linked contract is checked. Remaining runtime, platform and method evidence is tracked in [validation obligations](decisions.md#open). A pending external-benchmark schema changes only the provisional export adapter.

## Phases and implementation stages

These rows account for the frozen PRD's separate phase and construction-stage axes. They route to the owning design; they do not replace its rules or assert implementation acceptance.

| PRD phase (1.3) | Owning design and handoff | Acceptance boundary |
|---|---|---|
| Track 1: Phase 1 static research baseline | [Flow](flow.md), [research chain template](capabilities/README.md), [Codex bridge](system/environment.md#model-bridge), [lifecycle](system/lifecycle.md) | Release-critical static route and workflow; valid negative science reaches delivery |
| Track 2: required offline RSI validation | [RSI](rsi.md), [RSI engine](capsule/rsi-engine.md), [oracle](capsule/fixture-oracle.md) | Required M1 acceptance; isolated from live DAG and active-alias mutation |
| Track 3: Phase 2 dynamic test [tracks](system/experiments.md#term-track) | [Experimental whitelist](system/experiments.md), [planner](system/planner.md) | Isolated, non-blocking; external access approval precedes real alternate-model integration |

| PRD implementation stage | Design routing | Boundary that must be demonstrated by implementation |
|---|---|---|
| 0 (6.3): runtime unblocker and local configuration | [Integration](system/integration.md), [environment](system/environment.md), [auth](system/model-auth.md), [deployment](system/deployment.md) | Bounded Codex request under the selected secured configuration |
| 1 (6.4): governed execution backbone | [Runtime](runtime.md), [verification](verification.md), [runner](capsule/runner.md), [Gate host](capsule/gate-host.md), [storage](system/storage.md), [records](system/records.md), [lifecycle](system/lifecycle.md) | Valid A [releases](system/lifecycle.md#term-release) B; invalid A blocks B; headless halt returns durable machine status |
| 2 (6.5): intake, Brief and static DAG | [Intake](types/intake.md), [intent CC](capabilities/intent-compile.md), [requirement CC](capabilities/requirement-capsule.md), [planner](system/planner.md), [template plan](capabilities/README.md) | Submitted assets become accepted intent, a validated Brief, and frozen bindings for the [task DAG](types/run-plan.md#term-planned-plan) |
| 3 (6.6): evidence to hypothesis | [Search](capabilities/search-capsule.md), [Screening](capabilities/screening.md), [Hypothesis](capabilities/hypothesis.md) | Referenced ideas, one selected opportunity and pre-registered hypothesis cross real Gates |
| 4 (6.7): Builder and POC | [POC](capabilities/poc.md), [workspace](capabilities/op-workspace-io.md), [process boundary](capsule/process-boundary.md) | Bounded valid executable bundle and build evidence; no autonomous repair |
| 5 (6.8): benchmarking and scientific evaluation | [Benchmark](capabilities/benchmark.md), [protocol](capabilities/measurement-protocol.md), [Evaluation](capabilities/evaluation.md) | Positive and negative valid execution preserve separate scientific/infrastructure verdicts |
| 6 (6.9): delivery and complete research run | [Delivery](capabilities/delivery.md) | Complete request-to-report evidence and committed final result |
| 7 (6.10): operational shell | [Workstation](system/workstation.md), [observability](system/observability.md), [benchmark endpoints](system/benchmark-export.md) | Install, initialize, execute, inspect and retrieve through supported local interfaces |
| 8 (6.11): offline RSI | [RSI](rsi.md), [RSI engine](capsule/rsi-engine.md), [oracle](capsule/fixture-oracle.md), [admission](capsule/admission.md), [library activation](capsule/library.md) | Bounded improvement, hidden-data defense, guardrail evidence, human activation and rollback |
| 9 (6.12): isolated Phase 2 tests | [Experiments](system/experiments.md), [planner](system/planner.md), [routing](model-routing/README.md) | Permitted variants compared against operational baseline without modifying production acceptance |
| Handoff (6.13) | [Architecture index](README.md), [build order](build-order.md#from-these-docs-to-code-and-tasks), [modules](system/modules.md) | Every boundary has canonical fields, behavior, placement, evidence and validation hooks |

[Build order](build-order.md) is the home of the detailed construction dependencies. Its numbered engineering [steps](system/nodes.md#term-step) are not PRD stage identifiers; use the clause IDs above when allocating downstream tasks. Whitelist/blacklist checks require reading each heading's tracks, not assuming every inventoried heading is active M1 work.

### Coverage limits

The map has page links for all nine research stages, all three tracks and all ten construction stages. It is grouped navigation, not a claim of line-by-line requirement satisfaction. Stage 8 requires protected-set separation, guardrail execution and rollback evidence; stage 9 preserves the external-access gate and non-blocking status; their linked designs remain subject to source review. [Boundary cases](system/boundary-cases.md) routes negative scenarios; commands and results belong to implementation evidence.
