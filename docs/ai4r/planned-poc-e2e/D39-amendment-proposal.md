> Proposal only, pending Muk's approval. Nothing here is applied to docs/architecture.

# Proposal: amend D39, the Planner is the product default

Status: draft only. No repo file was edited. Date: 2026-10-30. Branch: ai4r/planned-poc-e2e.
Paths below are under `docs/architecture/design-package/` unless they start with `AGENTS.md`.

## 1. Proposed D39 text

Replaces the `## D39` section in `method/decisions.md` (line 160). Keeps the `Standard` tag.

> ## D39
>
> **Proposed amendment, pending Muk's approval (2026-10-30).**
>
> `Standard`. **`plan_source` chooses the plan, and the Planner is the product default.** The run request carries `plan_source`, either `planned` or `static`. The product entry defaults to `planned`. It is recorded in the run plan. No other setting, profile field or failure changes it. The static template is kept only for recorded benchmarks and RSI reproduction. A benchmark runner and an RSI replay pin `static` on the request. Reason: the Planner now completes a real run, so the product should use it. The static template stays frozen so that recorded baselines and RSI comparisons can be reproduced. The choice is still made before the run, in one place.
>
> What changes:
> - The default `plan_source` at the product entry moves from `static` to `planned`.
> - The build order "static first, then planned" ([D26](#d26)) no longer sets the default. It stays as build history.
>
> What stays:
> - `plan_source` is still the only switch, chosen before the run, never during it.
> - The static template stays frozen, hash-pinned and reproducible. Its contract, selectors ([D47](#d47)) and RSI promotion path ([D46](#d46)) do not change.
> - Both sources still produce the same frozen `run_plan` type through the same binder, gates, dispatch and storage ([D26](#d26)).
> - A failed or rejected Planner does not fall back to the static template. It halts with `plan_infeasible` ([D30](#d30)).
> - A static run still does not count as planned-mode acceptance. A planned run still does not replace Phase 1 acceptance ([D40](#d40)).
> - Library defaults do not change (see open question 1).
>
> Evidence (branch `ai4r/planned-poc-e2e`):
> - Commit `2aaf1e0da` makes the product entry capture new profiles as `planned`. The environment variable `JIUWENSWARM_M1_PLAN_SOURCE` overrides it. The benchmark-runner compose pins `static`.
> - Live run `pl11b` (2026-10-30) completed every stage on the planned path: Intent compiler, Planner, Search, Screening, Hypothesis, Builder, Benchmark, Evaluation and Delivery. Every node gate advanced. The trusted scorer gave accuracy 0.5 for the baseline and 1.0 for the treatment. Evaluation returned PASS. Run log: `docs/ai4r/planned-poc-e2e/RUN.md`. Fixes: `git log beb8780e2..HEAD`.
>
> Consequences:
> - Defaults that moved, at the product entry only: `plan_source` is `planned`, requirements is `m1-9` and screening is `m1-5`.
> - Defaults that did not move: the library defaults, and the benchmark and RSI paths, which pin `static`.
> - A benchmark or RSI replay that omits `plan_source` would now run planned. Their callers must pin `static` explicitly.
> - Phase 1 acceptance still uses the static template ([D40](#d40), [phases](phases.md)).
>
> Page: [run plan](../reference/run-plan.md).

Also update the index row at `method/decisions.md:71`:

- Current: `| D39 | The run setting plan_source (static or planned) is the only way to choose the plan source | Realizes §§1.3, 2.7. See [D39](#d39) |`
- Suggested: `| D39 | The run setting plan_source (planned or static) is the only way to choose the plan source. The product default is planned. The static template is kept for benchmarks and RSI reproduction | Realizes §§1.3, 2.7. See [D39](#d39) |`

## 2. Replacement for the AGENTS.md sentence

`AGENTS.md:64`, end of the D23 to D26 paragraph.

- Current: `Build the static DAG first, then the Planner, both producing the same frozen run plan.`
- Replace with: `The Planner (plan_source planned) is the product default (D39, amended 10-30). The static template is kept frozen for benchmarks and RSI reproduction. Both produce the same frozen run plan.`

The paragraph is headed "D23 to D26", and the new sentence cites D39. Muk may prefer a separate D39 sentence.

## 3. Other places to edit (follow-up, after approval)

### Priority A: states static as the default. Must change.

| File:line | Current text | Suggested text |
|---|---|---|
| `1-system.md:112` | `static` (the default) uses the **static template**, a hand-written plan. With the Intention Compiler it is the PRD's Phase 1 Default DAG. `planned` uses the **Planner node**. | `planned` (the product default) uses the **Planner node**. `static` uses the **static template**, a hand-written plan kept for benchmarks and RSI reproduction. With the Intention Compiler it is the PRD's Phase 1 Default DAG. |
| `reference/field-catalog.md:700` | enum `static`, `planned`. Default `static`. Under an evaluation profile it equals that profile's `plan_source` | enum `planned`, `static`. Default `planned` at the product entry. Benchmark and RSI requests pin `static`. Under an evaluation profile it equals that profile's `plan_source` |
| `reference/field-catalog.md:950` | `cc.plan_source` ... enum `static`, `planned`. Default `static` | Per open question 1. If it follows the product: `Default planned`. If it stays the library default: add `Library default. The product entry sets planned (D39)`. |
| `reference/run-plan.md:10` | A hand-authored **static template** (built first, the M1 default) and a **plan proposal** from the Planner (built second). | A hand-authored **static template** (built first, kept for benchmarks and RSI reproduction) and a **plan proposal** from the Planner (built second, the product default). |
| `reference/run-plan.md:22` | The run request carries `plan_source` (`static` or `planned`, default `static`) and nothing else selects it | The run request carries `plan_source` (`planned` or `static`, product default `planned`) and nothing else selects it |
| `reference/capsules/planner.md:222` | In M1 the fixed static template is the default and the Planner is the second build step. | In M1 the Planner is the product default. The static template was built first and stays for benchmarks and RSI reproduction. |
| `method/decisions.md:110` (D26) | **Static first, then planned.** The first runnable path is a hand-authored static template ... a working static path gives a baseline to debug the Planner against. | Keep as build history. Add at the end: `Amended by [D39](#d39) on 2026-10-30: the build order is history, and the product default is the Planner.` |
| `method/decisions.md:79` (D47 index row) | Realizes §2 (static default over any Brief) | Realizes §2 (static template over any Brief) |

### Priority B: wording that implies static is the baseline or default. Check and soften.

| File:line | Current text | Suggested text |
|---|---|---|
| `glossary.md:24` | `static` (the static template) or `planned` (the Planner node). Chosen before the run, on the run request (D39). The only plan-source switch | `planned` (the Planner node, the product default) or `static` (the static template, for benchmarks and RSI reproduction). Chosen before the run, on the run request (D39). The only plan-source switch |
| `glossary.md:25` | The hand-written plan used when `plan_source` is `static`. The PRD's Phase 1 Default DAG together with the Intention Compiler | Append: `Kept frozen for benchmarks and RSI reproduction.` |
| `method/decisions.md:87` (D19) | The M1 design supports a fixed Phase 1 static template and the targeted Phase 3 Planner path. | Optional. Add: `The product default is the Planner (D39).` |
| `1-system.md:218` | Phase 1, the governed baseline, is the static template, every gate and the fixed Codex route. It alone is the PRD's core M1 gate. | Keep. Add: `The product runs the Planner by default ([D39](method/decisions.md#d39)). The Phase 1 gate is still shown with the static template.` |
| `3-build-plan.md:16-17` | Step 3 `Static template over the six research nodes and Delivery`; step 4 `Planner CC and its checks` | Keep as build order. Add a note under the table: `Build order is not the run default. The product default is the Planner (D39).` |
| `3-build-plan.md:30` | With Codex available, run the same static template in each condition | Add `(pinned static)`. It is a reproducibility test. |
| `method/phases.md:23` | The static template is the Phase 1 baseline. A planned run demonstrates Phase 3 Dynamic Agent Planning and cannot substitute for Phase 1 acceptance. | Keep. Add: `The product default is the Planner (D39). Phase 1 acceptance still uses the static template.` |
| `method/phases.md:38` | The static template meets this exit. The Phase 3 Planner adds an explicit `plan_source: planned` route | The static template meets this exit. The Phase 3 Planner is the product default, selected with `plan_source: planned` |
| `pipeline/README.md:36` | The static template runs first and yields the same type | The static template was built first and yields the same type. The Planner is the product default (D39). |
| `platform/planning-and-freeze.md:9` | The static template is the Phase 1 baseline. | Append: `The Planner is the product default (D39).` |

### Priority C: checked, no edit needed

These stay true. They cover the RSI adoption path (D46), rejected-template rules (D30), the `3-build-plan.md:20` exit test with both sources, and "retained static workflow runs only when `plan_source` is `static`":
`side-systems/rsi-workbench.md:87,129,215`, `2-capability-capsules.md:9,88,117`, `platform/README.md:25,146`, `platform/planning-and-freeze.md:25,28,49,53,59,63`, `platform/failure-and-recovery.md:41`, `pipeline/intention-compiler.md:51,70`, `reference/field-catalog.md:952,1123`, `reference/run-plan.md` (lines 38, 297, 571, 588), `method/decisions.md:138`, `side-systems/model-routing.md:57`.

Out of scope: `docs/architecture/experiments/**` copies. They are frozen review records.

## Open questions for Muk

1. Should the operator config default `cc.plan_source` (`field-catalog.md:950`) also become `planned`? The brief says library defaults do not move, so this draft keeps it `static` and relies on the product entry. That leaves two defaults that differ. One default is simpler.
2. Should `m1-9` (requirements) and `m1-5` (screening) be named in the design package? This draft names them only in the D39 consequences. They are product-entry settings, not contracts.
3. Should the AGENTS.md sentence be its own D39 line instead of part of the D23 to D26 paragraph?
