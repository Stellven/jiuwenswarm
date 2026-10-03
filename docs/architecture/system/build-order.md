---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../m1/pipeline.md, observability.md]
provides: [system.build_order]
consumes: []
depends_on: [overview.md, observability.md, ../m1/pipeline.md, ../capsule/runner.md, ../capsule/gate-host.md, lifecycle.md]
tags: [system, build-order, process]
---

> **Draft, not yet approved.** The order in which M1 is built, and what blocks what. Written 2026-10-02 with Muk's direction. It is architecture, so it lives here, not in a proposal page.

# Build order

This page owns construction order; [pipeline](../m1/pipeline.md) owns execution order. [Runner](../capsule/runner.md) owns calls and [observability](observability.md) owns capture. PRD section 6 stages 0–9 remain the dependency sequence; calendar dates can differ. [Pipeline](../m1/pipeline.md) owns the minimal current capsule set. Mechanical helpers are ordinary modules.

**Strong recommendation: build one capsule, then one connected capsule, and prove the connection before building anything else.** Never build a dozen capsules in one pass. Never build the whole runner in one pass and then the dozen capsules on top of it. A defect in the runner or in a type then shows up inside twelve capsules at once, and no one can tell which layer is wrong.

Each step ends with an independently derived boundary check before dependent work begins. Parallel builders may work against pinned shared contracts after those are checked. The frozen PRD's [implementation order](../../product/prd-m1-full-2026-10-02.txt) remains the product dependency order.

| Step | Build | Needs first | Check, and how to run it | Unblocks |
|---|---|---|---|---|
| 1 | durability/config/admission foundation and pure extraction/IntentIR helpers; prepare a minimal admitted fixture capsule for runner invocation | [`source_text`](../types/source-text.md), [`intent_ir`](../types/intent-ir.md), [Declaration](../capsule/fields.md), [storage](storage.md) | pure helper output validates/repeats by hash; fixture call records bytes; changed fixture hash is refused until re-admitted; atomic write faults expose no partial authority | step 2 |
| 2 | `compile_brief` wired to prepared intake/source_text, optional IntentIR hints; first recorded model call | step 1; [research_brief](../types/research-brief.md) | inputs match committed preparation hashes; canary agrees on required ports; malformed source rejected before model call; recorded reply replays without network | step 3 |
| 3 | shared `research.verifier` and Gate host on Brief output | steps 1–2; [Gate host](../capsule/gate-host.md), pinned stage profile and verifier | deterministic violation fails; unknown semantic outcome does not pass; failed PASS persistence releases nothing | governed continuation |
| 4 | the run plan walking steps 1 to 3 with durable gate release | step 3; [lifecycle](../system/lifecycle.md) | kill the process between steps and resume; no step reruns, no result is lost | any longer chain |
| 5 | Search, three retrieval capabilities and Screening with ordinary rank helper | step 4; [search](../m1/search-capsule.md), [screening](../m1/screening.md) | wire checks; ranking/eligibility/tie fixtures; no eligible card halts truthfully | hypothesis |
| 6 | Hypothesis then POC | step 5; [measurement protocol](../m1/measurement-protocol.md), registered trusted methods | wire checks; preregistration and immutable resource snapshot | scientific execution |
| 7 | scientific Benchmark, Evaluation with ordinary predicate helper, Report | step 6; validated execution profile and canonical evaluation classification | wire checks; trusted measurements remain authority; middle-zone conditions preregistered | research chain |
| 8 | publication, local CLI/Web/TUI/tmux, retrieval, headless export and evidence reconstruction | complete research path and [workstation](workstation.md) | one local fixture run through report; scientifically negative valid run completes; interruption/restart and clients observe same records | production demonstration |
| 9 | required offline RSI, private oracle, bounded child target and human activation | admitted parent/library, validated isolation, [RSI](../capsule/rsi-engine.md) | mutation/fixture/referee/promotion attacks block and retain evidence; session/lifetime counters persist; no autonomous activation | complete required M1 acceptance |
| 10 | permitted isolated compiler/Leader/router/Code Mode experiments | operational comparison baseline; [experiments](experiments.md), [planner](planner.md) | plan rejection produces zero dispatch; production flags denied; mocked endpoints until approved access | non-blocking experiment evidence |

**Rules that follow from this.**

- **One new link per step.** Add one capsule, wire it to the one before, test the wire, then move on.
- **The runner grows with admitted fixtures and work capabilities.** Add features only when the next connected boundary requires them.
- **A seam is not proved by its two sides compiling.** It is proved when the producer's real output enters the consumer, and when a wrong output is refused. The canary and the hash comparison are how.
- **Defined boundaries unblock parallel work.** Build against canonical provisional adapters; runtime/security validation obligations block only affected execution profiles. Never claim an unsupported platform passed.
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
| capsule inventory | [pipeline](../m1/pipeline.md) |
| required offline RSI and isolated experiments | [RSI engine](../capsule/rsi-engine.md), [experiments](experiments.md) |
| complete seven-question cards | [handoff](handoff.md), [coder requirements](coder-requirements.md) |
