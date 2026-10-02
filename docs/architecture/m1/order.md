---
type: design
status: draft
tags: [design, draft, m1]
---

# M1: design order

> **Draft, architecture guidance.** How M1 is designed: define canonical types and producer/consumer seams before each module's observable behavior, in the order the PRD's main pipeline runs. The full PRD is copied at [`docs/product/prd-m1-full-2026-10-01.txt`](../../product/prd-m1-full-2026-10-01.txt).

## The rule

Design M1 in the PRD's order, one area at a time. First define its canonical input/output types and APIs at their single owning pages; then specify observable behavior, failure outcomes, gates, and producer/consumer agreement. Do not prescribe internal algorithms when the output contract suffices. Each area design is:

- its Declaration;
- its canonical input and output schemas;
- its API and effects, connected to producer and consumer seams;
- observable behavior, checks, failure outcomes, and acceptance evidence.

Spec Kit authoring and implementation details belong to the coding role after architecture contracts are ready.

## The first two capsules

| # | Capsule | PRD | Kind | Why here |
|---|---|---|---|---|
| 1 | [`requirement_capsule`](requirement-capsule.md) | 3.2 Requirement Compilation | skill | the first capsule on the main path. Every later stage reads its Research Brief. For RSI it is an easy target: the prompt and a table of defaults |
| 2 | [`research.screen_ideas`](screening.md) | 3.4 Screening | tool, with the pure helper [`op.rank_opportunities`](op-rank-opportunities.md) | current contract-first focus; behavior remains black-box pending issues 48–53 |

**Why this order:**

- **RSI compatibility is a cross-cutting seam.** Screening's tool kind and RSI's requested skill mutation target conflict; resolve that boundary before treating Screening as an RSI target (issue 50).
- **Model Routing gets real calls.** Requirement and Screening make model calls through the same broker/model API regardless of capsule kind.
- **Pure helpers stay fixed.** A pure helper such as `rank_opportunities` is pinned by its caller, and has `evolution.rsi: none`. The PRD's arithmetic never drifts while RSI tunes the judgement around it.

## After those

The rest follow the PRD's order:

1. `search_capsule` (3.3), already designed and checked;
2. `hypothesis_capsule` (3.5);
3. `poc_capsule` (3.6);
4. `benchmark_capsule` (3.7);
5. the scientific evaluation capsule, M20 (3.8) — not `verifier_capsule` (M09, the generic tier-2 judge used at every gate); see [m1-architecture.md](../m1-architecture.md#the-modules) Open 5 for why these are two different capsules despite the shared lineage;
6. `report_capsule` (3.9).

Ingestion (3.1) is deterministic control code, so it is a candidate for pure capsules later.

**`compile_intent`** is a built reference: a pure, deterministic `tool` capsule ([intent capsule](intent-capsule.md)). It shows the pure-tool pattern; another person may take it on.

## Relation to other pages

- [Capsule inventory proposal](capsule-inventory-proposal.md): a not-yet-adopted reduction of the M1 capsule set (one generic verifier, ingestion as launcher code, pure helpers folded into callers).
- [Current module/process map](../system/modules.md), [full run plan](pipeline.md) and [coverage](../prd/coverage.md) own the whole-M1 design. [M1 architecture](../m1-architecture.md) is historical; its M-numbers remain names only. Muk owns shared architecture/CC contracts and workstream owners retain product semantics.
- The 3.W answer (`prd/capsule-3w.md`) predates section 3 too.
