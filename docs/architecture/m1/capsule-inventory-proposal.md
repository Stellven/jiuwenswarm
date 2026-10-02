---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, pipeline.md, order.md, ../capsule/gate-capsules.md]
provides: []
consumes: []
depends_on: [pipeline.md, order.md, ../capsule/gate-capsules.md, ../capsule/gate-host.md, ../system/nodes.md]
tags: [m1, proposal, capsule, inventory]
---

> **Proposal, not adopted.** Nothing here changes a checked page. The current design stays as written in [pipeline](pipeline.md) until Muk approves and the change order below is run. Written 2026-10-02.

# Proposal: a smaller M1 capsule inventory

**The question.** The current design admits 35 capsules for M1. The PRD names nine. This page proposes 15, keeps the PRD's shapes, and keeps a few capsule-to-capsule hand-offs so the system can demonstrate that capsules compose.

**Where this sits.** [Pipeline](pipeline.md) owns the run plan and the capsule map. [Order](order.md) owns the design order and the RSI-drift reason for pinned helpers. [Gate capsules](../capsule/gate-capsules.md) owns the gate pattern. This page owns only the proposed delta. On adoption it is replaced by edits to those owners, and this page becomes a record.

## Count

| Group | Current | Proposed | Change |
|---|---|---|---|
| Work capsules | 11 | 9 | `extract_text` becomes launcher code; `deliver_report` merges into `write_report` |
| Gate capsules | 11 | 1 | one generic `verifier` |
| Pinned helper capsules | 11 | 5 | six helpers become library functions inside their callers; three workspace operations count as three |
| Shared prompt, router | 2 | 0 | `prompt.gate_judging` disappears with the gate collapse; the router waits for Model Routing |
| **Total** | **35** | **15** | |

The router is not counted either way until Model Routing delivers it (see [model routing reply](../model-routing/README.md)). With it, the proposal is 16.

## The proposed inventory

### Work capsules (9)

| Step | Capsule | Kind | Pins |
|---|---|---|---|
| intent | `research.compile_intent` | tool (pure) | none |
| requirement | `research.compile_brief` | skill | none |
| search | `research.search_ideas` | tool | `op.scholarly_search`, `op.local_search` |
| screening | `research.select_opportunity` | skill | `op.rank_opportunities` |
| hypothesis | `research.form_hypothesis` | tool, one model turn | `op.codesearch` |
| poc | `research.build_poc` | tool, model turns | `op.codesearch` |
| benchmark | `research.run_benchmark` | tool, no model | trusted measurement methods |
| evaluation | `research.evaluate_results` | tool, one model turn | `op.compare_to_thresholds` |
| report | `research.write_report` | skill | none |

### Gate (1)

`research.verifier`, a `skill` with `evolution.rsi: none`. It is the PRD's `verifier_capsule` (4.2, Tier 2). The run plan supplies each step's judged rubrics as inputs. See [gate collapse](#1-gates-eleven-to-one).

### Operators kept as capsules (5)

| Operator | Why it stays a capsule |
|---|---|
| [`op.scholarly_search`](op-scholarly-search.md), [`op.local_search`](op-local-search.md), [`op.codesearch`](op-codesearch.md) | they wrap external search tools and have effects |
| [`op.rank_opportunities`](op-rank-opportunities.md), `op.compare_to_thresholds` | pure helpers kept on purpose as composition examples; both are fixed arithmetic with `evolution.rsi: none` |

## What changes, and how

### 1. Gates: eleven to one

- **Today.** Every step has exactly one gate capsule ([nodes](../system/nodes.md#gates)). All eleven share one shape and one prompt, and differ only in name and rubric files ([gate capsules](../capsule/gate-capsules.md)).
- **Proposed.** One `research.verifier`. Each step's run-plan entry names the rubric files (by hash) the verifier judges against. The gate host still folds the verifier's answer with the deterministic checks and writes the Verification ([gate host](../capsule/gate-host.md)).
- **What stays.** Tier 1 (deterministic checks) and Tier 2 (one judge per criterion) are unchanged. The referee is still not RSI-able. A work capsule's own rubric stays in the work capsule.
- **What moves.** Rubric files live with the step's check entry, not in a per-step gate capsule body. The admission hash for a rubric attaches to the step check. The shared judging text becomes the verifier's `SKILL.md`, so `prompt.gate_judging` is no longer a separate capsule.
- **The source gate.** With `extract_text` as launcher code there is no `accept_source_text`. The launcher's output is validated by the `source_text` type check, with no gate step.
- **Risk.** The freeze check ([toolchain M03](../capsule/toolchain.md)) and the gate pattern assume a per-step gate capsule name. Both need a rule for "verifier plus rubric set", and the canary must show two blind derivations agree.

### 2. `extract_text`: launcher code

- **Today.** `research.extract_text` and `research.accept_source_text` ([extract text](extract-text.md)).
- **Proposed.** The launcher projects intake to `source_text` (PRD 3.1; [order](order.md) already calls ingestion deterministic control code). The type stays defined at [source text](../types/source-text.md). `compile_intent` still reads `source_text`, now from `launcher.source_text`.
- **Run plan.** Eleven steps become ten.

### 3. Report and deliver: merged

- **Today.** `write_report` (skill) and `deliver_report` (tool), with [`accept_report`, `accept_delivery`](research-gates.md) ([delivery](delivery.md)).
- **Proposed.** One `research.write_report` covering PRD 3.9.1 to 3.9.4. Raw benchmark delivery is a file-copy step with the same Gate. Run plan: ten steps become nine.
- **Risk.** Delivery was a fixed-only Gate (open issue 36). Merging it means the report step's Gate has a judged part and a fixed part, and the fixed part must still run.

### 4. Pure helpers: library functions

| Helper | Becomes | Inside |
|---|---|---|
| [`op.assess_dependency`](op-assess-dependency.md) | library function | `select_opportunity` |
| `op.freeze_resources` | trusted-service call | `form_hypothesis` |
| `op.syntax_check` | trusted-service call | `build_poc` |
| `op.workspace_read`, `op.workspace_write`, `op.workspace_list` ([op-workspace-io](op-workspace-io.md)) | library functions | `build_poc` |

**Trust rule, so nothing silently weakens.** [`op.freeze_resources` and `op.syntax_check`](measurement-protocol.md) are the trusted snapshot service and the fixed compiler and AST scan. They must run on the trusted side of the [measurement authority](measurement-protocol.md#trusted-measurement-authority), never inside the generated code's confined process. Folding them in changes where the call is written, not who executes it.

**What is given up.** A helper pinned as a capsule had its own `decl_hash`, so RSI could not change it. A library function is covered only by the caller's body hash. For `assess_dependency` and the workspace operations the policy registry is frozen outside the caller ([op-assess-dependency](op-assess-dependency.md)), so the loss is small. `rank_opportunities` and `compare_to_thresholds` stay capsules because they carry the PRD's arithmetic that must not drift.

## The composition examples

Three hand-offs stay as the demonstration that capsules compose and that types connect:

| # | Flow | What it shows |
|---|---|---|
| 1 | `compile_intent` to `compile_brief` | a pure tool feeding a skill, across the `intent_ir` type |
| 2 | `search_ideas` to `op.rank_opportunities` to `select_opportunity` | a skill calling a pinned pure helper across `screening_assessments` and `opportunity_card` |
| 3 | `run_benchmark` to `evaluate_results`, which pins `op.compare_to_thresholds` | arithmetic the model cannot change, across `benchmark_payload` and `evaluation_verdict` |

## PRD map

| PRD capsule | Proposed capsule |
|---|---|
| ingestion (3.1, not a capsule) | launcher code |
| `requirement_capsule` | `compile_brief` (plus `compile_intent`, a CC preparation step) |
| `search_capsule` | `search_ideas` |
| `screening_capsule` | `select_opportunity` |
| `hypothesis_capsule` | `form_hypothesis` |
| `poc_capsule` | `build_poc` |
| `benchmark_capsule` | `run_benchmark` |
| `scientific_evaluator_capsule` | `evaluate_results` |
| `report_capsule` | `write_report` |
| `verifier_capsule` | `research.verifier` |

## Build order

Moved to its owner, [build order](../system/build-order.md). It applies to whichever capsule set is adopted.

## Benchmark harness requests: headless entry and config-assembled components

The benchmarking workstream asked for two development-only features. Neither is in the PRD's product roadmap. Both change the early build steps, so they are placed here. Product owners keep the decision on whether they ship; architecture only says where they land.

### Request 1: a headless run that halts without a human

**Ask.** A programmatic entry taking a task, a config and a seed. It runs the pipeline and returns the result and a run directory. Where a gate failure would open `human_session`, a headless flag records the halt in the run tree and exits with a status code instead.

**What exists.** [Workstation](../system/workstation.md#cli-and-public-run-api) already gives `jiuwenswarm cc run`, `POST /cc/runs`, run states, and exit code 3 for a halted run. [Lifecycle](../system/lifecycle.md#human-review-and-recovery) already says a non-interactive terminal leaves the run halted with the review requirement exposed.

**What is missing.**

| Gap | Proposed landing | Owner page |
|---|---|---|
| a `--headless` flag (and `headless: true` on `POST /cc/runs`) that skips opening `human_session` and records the halt record directly | the halt host writes the same halt record and review requirement it writes today, then does not open the session; exit code 3 | [lifecycle](../system/lifecycle.md) |
| a `seed` input | one `seed` in the request, pinned in the run's configuration snapshot ([storage](../system/storage.md)), and recorded as the root of the blueprint's seed policy | [workstation](../system/workstation.md), [environment](../system/environment.md) |
| a per-run `config` argument | an overlay file passed with the request, merged as a layer above project `config.yaml`, and pinned by `begin_run` like any snapshot | [environment](../system/environment.md#effective-configuration) |
| a return value of result plus run directory | `RunView.output_refs` plus a stable `run_dir` path in the JSON reply | [workstation](../system/workstation.md) |

**Rules.**

- The flag changes how a halt is surfaced, never whether the gate decides. A headless run still stops at the same gate, with the same Verification.
- Resume stays terminal-only. A headless halt is final for that run; the harness starts a new run.
- Mark the flag development-only in the config, so a headless run is recorded as such in its snapshot. A product run can never silently become headless.

### Request 2: components wired from config

**Ask.** The ablation study runs the same code with one component removed at a time. Capsules, the router, the evaluator gate and RSI must be wired from config, not hard-coded. The harness must pin the capsule library to a snapshot hash and read that hash back from the run output.

**What exists.** `cc.plan_path` already names the run plan, and the run plan binds capsules by admitted hash ([pipeline](pipeline.md#plan-compilation)). The configuration snapshot is pinned per run. The library is versioned and append-only ([library](../capsule/library.md)).

**What is missing.**

| Component | Proposed config | Note |
|---|---|---|
| capsules | the run plan chooses them; a config key selects the plan, so an ablation plan omits or swaps one step | [run plan type](../types/run-plan.md) |
| library snapshot | `cc.library.snapshot_sha256`: the run refuses any capsule whose admitted hash is not in that snapshot; the same hash is written into the run's `ConfigSnapshot` and returned in `RunView` | needs a snapshot object in [library](../capsule/library.md) and a field in the run view |
| router | `cc.router.enabled`; off means the runner's default model call ([seams](../seams.md#model-routing)). The router is not on the M1 path yet, so this key waits for Model Routing | |
| RSI | `cc.rsi.enabled`; off means no RSI session opens and no Candidate is accepted | [RSI engine](../capsule/rsi-engine.md) |
| evaluator gate | `cc.gates.evaluator`: `on` (product) or `off` (development ablation) | see the conflict below |

**Conflict to decide.** The design rule `every_step_gated` and INV-8 say no step is accepted without a gate, and the referee is never RSI-able. An evaluator-gate-off ablation breaks the first rule on purpose. The proposal: allow it only in a profile named `ablation`, record that profile in the run's snapshot, and have every output of such a run carry `ablation: true`, so it can never be taken for a product result. The harness's report must say which gate was off.

**Rule.** A component switched off in config is absent from the run, never stubbed to pass. The run output states which components ran and the library snapshot hash, so the harness can prove it.

### Request 3: stage, role and capsule id on each model call

**Ask.** Each outgoing model call carries pipeline stage, role and capsule id in a field a proxy can read. The security objection raised in reply is that the model API should not learn what the system is doing, and an observability layer should trace it instead.

**Already in the design.** The runner builds a [`ModelCallContext`](../capsule/runner.md) for every turn: `obs_id`, `turn`, `capsule_name`, `decl_hash`, `step_id` and `role` (role unchecked at M1). The protected [model bridge](../system/environment.md#model-bridge) request carries only `request_id`, `run_id` and `obs_id`, with prompt and reply stored by hash. Every turn is written to the Observation's `ext.runner.turns`. So the context exists and is recorded, but it stays inside CC. It is not sent to the model endpoint.

**Proposed disposition: trace, do not tag.** This agrees with the security objection.

- The wire to the model carries no stage, role or capsule field. The bridge is the only caller of the model, and it forwards the prompt only.
- Attribution is by join. A benchmark proxy or log reads the bridge's `request_id` and `obs_id`, and joins them to the Observation, which names the step, capsule and role. [Observability](../system/observability.md) owns that join, and `route_id` already joins routing decisions to turns the same way.
- If a proxy sits between the bridge and a real endpoint, it sees only `request_id`. It cannot attribute a call alone, and that is intended.

**Dev-only option, if the benchmark needs the proxy to see the context live.** Let the bridge emit a trace event (not an HTTP header or prompt field) to a local observability sink, keyed by `request_id`: `{request_id, run_id, obs_id, step_id, capsule_name, decl_hash, role, turn}`. It is never forwarded upstream, and the `cc.telemetry` flags in [environment](../system/environment.md) control it. This gives the benchmark its proxy view with no change to what the model API receives.

**Open for Muk and the Model Routing owner.** Confirm that the router's gateway mode (`route_record_id`, an endpoint that routes itself) does not need the context on the wire. If it does, that is a separate, explicit decision with its own threat note.

### Effect on the build order

- The `seed` and the snapshot hash are in the run record from step 1, because they sit in the configuration snapshot the first runner slice already pins. Adding them later changes the record shape.
- The headless flag lands with step 4 (durable gate release), where halting is first built.
- The ablation switches land after step 7, once there is a full run to remove components from. The router switch waits for Model Routing.
- The attribution answer (request 3) is recorded as decisions D14 and D15. Requests 1 and 2 are new open decisions for the owners of lifecycle, environment and library; they are not recorded in [decisions](../decisions.md) yet.

## Change order if adopted

Follow [PROCESS](../PROCESS.md#the-order-for-changing-anything). Owner first, consumers after.

1. **Record** the decision in [decisions](../decisions.md) (D-row with the gate, ingestion, report and helper changes, and the trust rule).
2. **Owners:**
   - gate pattern: [gate capsules](../capsule/gate-capsules.md), [gate host](../capsule/gate-host.md), [toolchain M03](../capsule/toolchain.md);
   - run plan: [run plan type](../types/run-plan.md), [nodes](../system/nodes.md);
   - measurement trust: [measurement protocol](measurement-protocol.md).
3. **Lint** until `ok`.
4. **Consumers:**
   - gates: [intent gate](intent-gate.md), [brief gate](brief-gate.md), [search gate](search-gate.md), [screening gate](screening-gate.md), [research gates](research-gates.md), and the [gate area review](../reviews/2026-10-01-gate-area-review.md);
   - work capsules: [intent](intent-capsule.md), [requirement](requirement-capsule.md), [search](search-capsule.md), [screening](screening.md), [hypothesis](hypothesis.md), [poc](poc.md), [benchmark](benchmark.md), [evaluation](evaluation.md), [delivery](delivery.md);
   - source and helpers: [extract text](extract-text.md) (becomes a launcher spec), [op-assess-dependency](op-assess-dependency.md), [op-workspace-io](op-workspace-io.md).
5. **Module and seam pages:** [pipeline](pipeline.md), [diagram](../system/diagram.md), [seams](../seams.md), [types index](../types/types.md), [modules](../system/modules.md).
6. **Indexes:** [README](../README.md), [coverage](../prd/coverage.md).
7. **Canary:** re-run the area loop for gates, and the seam canaries for the three composition examples above.

Every page above that is `checked` reopens to `draft`. That is the real cost of the proposal.

## Open questions for Muk

- Keep `compile_intent` as its own capsule (this proposal), or fold it into `compile_brief` or the launcher and drop to 14? It is the one built pure-tool reference, so this proposal keeps it.
- Does the merged report step keep two Gate profiles (judged report, fixed delivery), or one combined profile?
- Does `research.verifier` take rubrics as inputs, or does the host render them into the prompt? The first keeps the capsule opaque to rubric content; the second is simpler.
- Count the router, once it exists, as M1 or as Model Routing's?

## Not changed by this proposal

[Coverage](../prd/coverage.md) still maps every PRD clause to a stage, and the PRD's capsule names (requirement, search, screening, hypothesis, poc, benchmark, scientific evaluator, report, verifier) all remain present. The two blocked boundaries in [black boxes](../system/blackboxes.md) are untouched.
