---
type: design
status: draft
tags: [design, draft, m1]
---

# M1: design order

> **Draft, architecture guidance.** How M1 is designed: one capsule at a time, in the order the PRD's main pipeline runs. The PRD's section 3 is copied at [`docs/product/prd-m1-section3.md`](../../product/prd-m1-section3.md).

## The rule

Design M1 in the PRD's order, one capsule at a time. Finish each capsule's design before starting the next. Each design is:

- its Declaration;
- its `make_capsule.md`;
- the payload schema it produces;
- its checks and test fixtures.

## The first two capsules

| # | Capsule | PRD | Kind | Why here |
|---|---|---|---|---|
| 1 | [`requirement_capsule`](requirement-capsule.md) | 3.2 Requirement Compilation | skill | the first capsule on the main path. Every later stage reads its Research Brief. For RSI it is an easy target: the prompt and a table of defaults |
| 2 | `screening_capsule` | 3.4 Screening | skill, with the pure helper `rank_opportunities` (3.4.7) | a harder RSI target: a scoring rubric whose quality is measurable on fixtures with known good picks. The ranking arithmetic stays fixed |

**Why this order:**

- **RSI proves itself step by step.** First on something easy, then on something a bit harder. Both capsules allow RSI (`evolution.rsi: propose`), and each lists exactly which files RSI may change.
- **Model Routing gets real calls.** Both capsules are model skills, so routing is attempted on genuine model calls from the start.
- **Pure helpers stay fixed.** A pure helper such as `rank_opportunities` is pinned by its caller, and has `evolution.rsi: none`. The PRD's arithmetic never drifts while RSI tunes the judgement around it.

## After those

The rest follow the PRD's order:

1. `search_capsule` (3.3);
2. `hypothesis_capsule` (3.5);
3. `poc_capsule` (3.6);
4. `benchmark_capsule` (3.7);
5. the scientific evaluation capsule, M20 (3.8) — not `verifier_capsule` (M09, the generic tier-2 judge used at every gate); see [m1-architecture.md](../m1-architecture.md#the-modules) Open 5 for why these are two different capsules despite the shared lineage;
6. `report_capsule` (3.9).

Ingestion (3.1) is deterministic control code, so it is a candidate for pure capsules later.

**`compile_intent`** is a built reference: a pure, deterministic `tool` capsule ([example](../capsule/example-compile-intent.md)). It shows the pure-tool pattern; another person may take it on.

## Relation to other pages

- [M1 architecture](../m1-architecture.md) is the whole-M1 build design: the system graph, the run graph, the payload table and all 27 modules (M00a-c, M01-M19, M07a-e, M10a), one issue each. It predates PRD section 3 and is being audited against it batch by batch, in the build order it already draws (see `tundle/obby/HANDOFF.md` for progress) — build from the audited modules; an unaudited one still needs its PRD cross-check first.
- The 3.W answer (`prd/capsule-3w.md`) predates section 3 too.
