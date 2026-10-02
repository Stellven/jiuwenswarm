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

## Build order: what comes first and what blocks what

**Strong recommendation: build one capsule, then one connected capsule, and prove the connection before building anything else.** Never build a dozen capsules in one pass. Never build the whole runner in one pass and then the dozen capsules on top of it. A defect in the runner or in a type then shows up inside twelve capsules at once, and no one can tell which layer is wrong.

Each step below is small, ends with a check that someone other than the builder can run, and unblocks the next. Do not start a step until the one before it passes its check. The PRD's own [implementation order](../../product/prd-m1-full-2026-10-01.txt) (section 6, Stage 0 to 9) stays the product order; this is the order inside it, and it refines it where the PRD lists whole stages.

| Step | Build | Needs first | Check, and how to run it | Unblocks |
|---|---|---|---|---|
| 1 | `compile_intent` alone, plus only the runner slice it needs: load a Declaration, admit its hash, call it, record the call. No model, no gate | the [`source_text`](../types/source-text.md) and [`intent_ir`](../types/intent-ir.md) types; the [declaration fields](../capsule/fields.md) | the output validates against `intent_ir`; the same input twice gives the same output hash; a changed body gives a different hash and is refused until re-admitted. Run through the [verification invocations](../system/verification.md) | step 2 |
| 2 | `compile_brief`, wired to step 1's `intent_ir`. The first model call, recorded so it replays | step 1 passing; the [research_brief](../types/research-brief.md) type | **the communication test:** step 2's input is byte-identical to step 1's published output (compare hashes); `python docs/architecture/_tools/arch_lint.py canary --producer A.json --consumer B.json --wire OUT=IN` agrees; a deliberately bad step 1 output is refused by step 2's input check, not passed on; the model call replays with no network | step 3 |
| 3 | `research.verifier`, run on step 2's output. The first gate | steps 1 and 2; the [gate host](../capsule/gate-host.md) | an output that satisfies its criteria passes; one that violates a deterministic check fails with that check's code; one the judge cannot evaluate does not pass (INV-8) | the rest. Every later step is gated, so nothing after this is accepted without it |
| 4 | the run plan walking steps 1 to 3 with durable gate release | step 3; [lifecycle](../system/lifecycle.md) | kill the process between steps and resume; no step reruns, no result is lost | any longer chain |
| 5 | composition example 2: `search_ideas`, `op.rank_opportunities`, `select_opportunity` | step 4; the [search](search-capsule.md) gate criteria; screening decisions 48 to 53 for `select_opportunity` | the same wire check on `idea_set` into the helper and `screening_assessments` into the card; the helper's arithmetic matches a hand-computed fixture | hypothesis |
| 6 | `form_hypothesis`, then `build_poc`, one at a time | step 5; decisions 41 and 58; the [measurement protocol](measurement-protocol.md) | the wire check at each link; the frozen-resource snapshot is immutable | benchmark |
| 7 | `run_benchmark`, then `evaluate_results` with `op.compare_to_thresholds` (composition example 3), then `write_report` | step 6; a validated execution profile (open issues 40 and 57); decision 44 | the wire check at each link; the stdout is not measurement authority, the trusted method's evidence is | end-to-end M1 |

**Rules that follow from this.**

- **One new link per step.** Add one capsule, wire it to the one before, test the wire, then move on.
- **The runner grows with the capsules.** Step 1 builds only what `compile_intent` calls. Each later step adds the runner features that step needs and nothing more.
- **A seam is not proved by its two sides compiling.** It is proved when the producer's real output enters the consumer, and when a wrong output is refused. The canary and the hash comparison are how.
- **Blocked work waits, it is not guessed.** Steps 5 to 7 name their open issues. The platform black boxes in [black boxes](../system/blackboxes.md) block only generated-code execution on the affected platform, so steps 1 to 5 proceed on Linux.
- **Model Routing is not on this path.** The runner's default model call serves steps 2 onward ([seams](../seams.md#model-routing)).
- **Who builds.** Muk owns the architecture and shared CC. A coder takes one step at a time. Each step's check is written before the build, by someone other than the builder (INV-9, INV-10).

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
