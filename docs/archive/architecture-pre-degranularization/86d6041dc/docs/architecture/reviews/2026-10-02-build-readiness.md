---
type: review
status: draft
version: 1
owner: muk
sources: [../README.md, ../PROCESS.md, ../system/modules.md, ../system/build-order.md, ../capsule/runner.md, ../capsule/toolchain.md, ../schemas/policy.md, ../m1/pipeline.md]
tags: [review, handoff, structure]
---

# Review: is the vault structured and specified enough to build from, 2026-10-02

**Historical sample before the frozen-baseline revision.** The findings below concern that earlier state, including its old Opus requirement. Current review uses [policies](../policies.md), [coder requirements](../system/coder-requirements.md) and the final revision evidence; this sample does not certify the revised handoff.

One read of the vault's structure, then spot checks of a storage module, a skill capsule, the runner's prompt contract, policy and the module map. This is a sample, not a full audit. Two layers consume this design: coders who build modules, and a later layer that turns the design into the prompts the models follow.

## Verdict

**The structure is logical and the specification is deep. It is not yet ready to hand to coders, for reasons of state and packaging, not of ideas.** A coder could start the first slice (build-order steps 1 to 4) from the runner, store, gate host and lifecycle pages. They would have to assemble each module from many pages, and almost none of the pages they need is marked `checked`.

## What is strong

- **A clear layering.** PRD, then `system/` (where it runs), `capsule/` (what a capsule is and how it runs), `schemas/` and `types/` (the data), `m1/` (this product), then `seams.md`, `decisions.md` and `open-issues.md`. One definition per datatype, with a table of where each lives.
- **A process that can fail.** Statuses, a lint, a blind canary, one Opus review, and a system diagram that must stay drawable.
- **Real API depth.** The runner defines the prompt envelope, the reply grammar, the parse rules, every failure code. The store defines layout, atomic publication, errors and crash cases. Policy gives values for the first epoch.
- **A build order built for coders.** One capsule, then one connected capsule, with a check someone else can run for each step.
- **A clean line below us.** The runner builds the prompt envelope. The prompt layer writes only the skill text, references and fixtures.

## What blocks a handoff

| # | Finding | Evidence | What to do |
|---|---|---|---|
| 1 | **Almost nothing the first slice needs is `checked`.** 9 pages are `checked` out of about 130. `fields.md`, `policy.md` and `verification-record.md` are `proposed`. The runner, toolchain, gate host, lifecycle, storage, records, environment, pipeline and the intent capsule and gate are `draft`. The 10-01 handoff expansion reopened them. | status of each page | Run the area loop again on the slice-1 pages only, in dependency order. Then lock them. `v1` starts when code starts, as the README says |
| 2 | **There is no per-module card.** A module's seven answers (placement, API, control, persistence, security, environment, verification) are spread over 3 to 10 pages. The module map links one or two per row | `system/modules.md` | One card per slice-1 module: purpose, owner page for each of the seven answers, errors, acceptance case ids. Generate it from front matter where possible |
| 3 | **Schemas are prose and compiled in the lint, but not delivered.** The types compile and validate in the lint, yet there are no exported JSON Schema files. Policy is a table, not a `policy.json`. Coders will re-derive them by hand | `find` shows no `*.schema.json` or `policy*.json` | Have the lint export every type's schema and the first-epoch policy and vocabulary as files, hashed. Code imports them. This is the strongest "schema first" step left |
| 4 | **The capsule set is undecided.** 35 capsules in the pipeline, 15 in the inventory proposal, which is not adopted. A coder cannot plan beyond capsule 4 | `m1/capsule-inventory-proposal.md` | Muk decides. Until then, steps 5 to 7 stay provisional |
| 5 | **Stale designs sit at the root.** `m1-architecture.md` (53 KB, status `draft`, not `past`), `b1-design.md` (39 KB, no status), `m1-design.md`, plus not-ours `OVERVIEW.md` and `m1.md`. The old module ids M01 to M14 are still used as names, so a reader meets two numbering systems | README "Past designs" | Move past designs to `archive/` with `status: past` in front matter. Give the module ids one owner page, the module cards |
| 6 | **Two reading orders in the README.** A ten-step order, then a "Current coding-handoff design" paragraph at the bottom that says where to start | README | Split it: "Build from these" for coders, "Understand the design" for reviewers |
| 7 | **Check two large pages for separable parts.** `runner.md` (68 KB) and `guards.md` (62 KB). Size alone is not a defect: there is no byte limit (Muk, 2026-10-02) | page sizes | Split only where a page holds separable concepts, or where two parts restate each other and risk two sources of truth. Needs Muk's sign-off |
| 8 | **The prompt layer had no brief.** Only the requirement capsule says what its skill must do, and in scattered sections. Other skills and the gate rubrics said less | `m1/*-capsule.md` | Added [prompt brief](../capsule/prompt-brief.md): the line between us and them, what the runner already does, and the rows each model-backed capsule page must add. Capsule pages still need their briefs written |

## Fixes made today

| Finding | Done |
|---|---|
| 1 status | Not done. The area loop must run again on the slice-1 pages, then lock them. Needs time and Muk's approval of each lock |
| 2 module cards | [`system/handoff.md`](../system/handoff.md): cards for build-order steps 1 to 4, plus what is ready and what is not |
| 3 schemas | `_tools/arch_lint.py` now generates [`exports/`](../exports/manifest.json): a JSON Schema for each of the 20 payload types, the records and the Declaration, with hashes. The lint fails if they go stale. The policy epoch stays a JSON file the coder writes from the policy page, by design (M00c) |
| 4 capsule set | Not done. Muk decides. Slice 1 does not depend on it |
| 5 stale designs | `m1-architecture`, `b1-design` and `m1-design` moved to [`archive/`](../archive/m1-design.md), `status: past`, links rewritten, lint exemption updated |
| 6 README | Split into "Build from these" and "Understand the design" |
| 7 large pages | No byte limit now (Muk). `runner.md` and `guards.md` are to be checked for separable parts only |
| 8 prompt layer | [`capsule/prompt-brief.md`](../capsule/prompt-brief.md), plus briefs in [`requirement-capsule`](../m1/requirement-capsule.md#prompt-brief) and [`screening`](../m1/screening.md#prompt-brief). The gate pages already hold their draft text. Hypothesis, POC, evaluation and report writer wait until their pages are firm |

## Still to do

1. Run the area loop again on slice 1 (finding 1), then lock.
2. Muk decides the capsule set (finding 4).
3. Write prompt briefs for hypothesis, POC, evaluation and the report writer once those pages are firm.
4. Split `runner.md` or `guards.md` only if a check finds separable parts or duplicated truth.

## Fact check of the new pages

One Opus agent checked the handoff page, the prompt briefs and the exports against their sources. It found six defects. All were verified and fixed, except the first one below, which is a design question.

- **Open, for Muk:** the [screening](../m1/screening.md) contract says `NO_ELIGIBLE_OPPORTUNITY` propagates from the helper, but the runner gives a skill only `CAPSULE_ERROR` and three `INPUT_*` issue codes. How a skill passes on a helper's reason is undefined.
- **Fixed:** the exported Declaration schema was almost empty and several list items were closed empty objects. The generator now adds parent objects and named shapes (`Port`, `Predicate`), and leaves prose-only list items open with a note. The Declaration examples on five pages now validate against it.
- **Fixed:** the `compile_brief` brief named the wrong checks. The prompt brief overstated two runner limits. Slice 1 left out `prompt.gate_judging`. Plan-script path differed between pages. Record schemas had an empty version.

## What I could not check

The sample covers storage, the requirement capsule, the runner's skill handler, policy and the module map. I did not read the security pages, the RSI pages, observability or the measurement protocol. I did not run a canary. Whether two coders would build modules that connect is exactly what the canary tests, and it has been run on one seam only (POC to Benchmark).
