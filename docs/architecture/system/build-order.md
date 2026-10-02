---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../m1/pipeline.md, observability.md]
provides: [system.build_order]
consumes: []
depends_on: [overview.md, observability.md, ../m1/pipeline.md, ../capsule/runner.md, ../capsule/gate-host.md, lifecycle.md]
tags: [system, build-order, process]
---

> **Draft, not yet approved.** The order in which M1 is built, and what blocks what. Written 2026-10-02 with Muk's direction. It is architecture, so it lives here, not in a proposal page.

# Build order

This page owns the order of construction. The [pipeline](../m1/pipeline.md) owns the run plan, the [runner](../capsule/runner.md) owns call execution, and [observability](observability.md) owns what is recorded. The PRD's own order is Stage 0 to 9 in section 6 of the [full PRD](../../product/prd-m1-full-2026-10-01.txt); this page refines it inside each stage. The capsule set it builds is the one in [pipeline](../m1/pipeline.md), or the smaller set in the [inventory proposal](../m1/capsule-inventory-proposal.md) if that is adopted.

**Strong recommendation: build one capsule, then one connected capsule, and prove the connection before building anything else.** Never build a dozen capsules in one pass. Never build the whole runner in one pass and then the dozen capsules on top of it. A defect in the runner or in a type then shows up inside twelve capsules at once, and no one can tell which layer is wrong.

Each step below is small, ends with a check that someone other than the builder can run, and unblocks the next. Do not start a step until the one before it passes its check. The PRD's own [implementation order](../../product/prd-m1-full-2026-10-01.txt) (section 6, Stage 0 to 9) stays the product order; this is the order inside it, and it refines it where the PRD lists whole stages.

| Step | Build | Needs first | Check, and how to run it | Unblocks |
|---|---|---|---|---|
| 1 | `compile_intent` alone, plus only the runner slice it needs: load a Declaration, admit its hash, call it, record the call. No model, no gate | the [`source_text`](../types/source-text.md) and [`intent_ir`](../types/intent-ir.md) types; the [declaration fields](../capsule/fields.md) | the output validates against `intent_ir`; the same input twice gives the same output hash; a changed body gives a different hash and is refused until re-admitted. Run through the [verification invocations](../system/verification.md) | step 2 |
| 2 | `compile_brief`, wired to step 1's `intent_ir`. The first model call, recorded so it replays | step 1 passing; the [research_brief](../types/research-brief.md) type | **the communication test:** step 2's input is byte-identical to step 1's published output (compare hashes); `python docs/architecture/_tools/arch_lint.py canary --producer A.json --consumer B.json --wire OUT=IN` agrees; a deliberately bad step 1 output is refused by step 2's input check, not passed on; the model call replays with no network | step 3 |
| 3 | `research.verifier`, run on step 2's output. The first gate | steps 1 and 2; the [gate host](../capsule/gate-host.md) | an output that satisfies its criteria passes; one that violates a deterministic check fails with that check's code; one the judge cannot evaluate does not pass (INV-8) | the rest. Every later step is gated, so nothing after this is accepted without it |
| 4 | the run plan walking steps 1 to 3 with durable gate release | step 3; [lifecycle](../system/lifecycle.md) | kill the process between steps and resume; no step reruns, no result is lost | any longer chain |
| 5 | composition example 2: `search_ideas`, `op.rank_opportunities`, `select_opportunity` | step 4; the [search](../m1/search-capsule.md) gate criteria; screening decisions 48 to 53 for `select_opportunity` | the same wire check on `idea_set` into the helper and `screening_assessments` into the card; the helper's arithmetic matches a hand-computed fixture | hypothesis |
| 6 | `form_hypothesis`, then `build_poc`, one at a time | step 5; decisions 41 and 58; the [measurement protocol](../m1/measurement-protocol.md) | the wire check at each link; the frozen-resource snapshot is immutable | benchmark |
| 7 | `run_benchmark`, then `evaluate_results` with `op.compare_to_thresholds` (composition example 3), then `write_report` | step 6; a validated execution profile (open issues 40 and 57); decision 44 | the wire check at each link; the stdout is not measurement authority, the trusted method's evidence is | end-to-end M1 |

**Rules that follow from this.**

- **One new link per step.** Add one capsule, wire it to the one before, test the wire, then move on.
- **The runner grows with the capsules.** Step 1 builds only what `compile_intent` calls. Each later step adds the runner features that step needs and nothing more.
- **A seam is not proved by its two sides compiling.** It is proved when the producer's real output enters the consumer, and when a wrong output is refused. The canary and the hash comparison are how.
- **Blocked work waits, it is not guessed.** Steps 5 to 7 name their open issues. The platform black boxes in [black boxes](../system/blackboxes.md) block only generated-code execution on the affected platform, so steps 1 to 5 proceed on Linux.
- **Observability grows the same way.** Records first, keyed by `obs_id`. Only an emit-and-subscribe bus skeleton arrives with the first gate; the real events, sinks and tracer come after. Step 1 may use a stub reservation counter until the supervisor lands at step 4. Owner and per-step additions: [observability](../system/observability.md#build-order-for-observability), decisions D14 to D16 in [decisions](../decisions.md).
- **Model Routing is not on this path.** The runner's default model call serves steps 2 onward ([seams](../seams.md#model-routing)).
- **Who builds.** Muk owns the architecture and shared CC. A coder takes one step at a time. Each step's check is written before the build, by someone other than the builder (INV-9, INV-10).

## Where requirements that change this order are owned

| Requirement | Owner page |
|---|---|
| records, `obs_id`, event bus, spans | [observability](observability.md) |
| halt, resume, headless halt | [lifecycle](lifecycle.md) |
| run entry, seed, exit codes | [workstation](workstation.md) |
| configuration keys, library snapshot hash, component switches | [environment](environment.md), [library](../capsule/library.md) |
| capsule inventory | [pipeline](../m1/pipeline.md), and the [proposal](../m1/capsule-inventory-proposal.md) |
