---
id: cap.op-rank-opportunities
type: module
status: draft
version: 3
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [op.rank_opportunities]
consumes: [cc.type.screening_assessments, cc.type.opportunity_card]
depends_on: [screening.md, op-assess-dependency.md]
tags: [m1, module, ranking]
level: detail
prd: [3.4.6, 3.4.7, 4.4.3]
---

# Ordinary rank_opportunities helper

PRD: 3.4.6, 3.4.7, 4.4.3

> Answers: How are assessed candidates ranked and one opportunity card selected?

## What it does

A local pure helper that ranks the assessed candidates and returns the selected `opportunity_card`.

## Interface

Local pure callable `rank_opportunities(assessments, dependency_registry_ref) -> opportunity_card` lives with the Screening implementation, pinned by its body hash. It is not a separately admitted capability. Input/output fields are defined in [screening_assessments](../types/screening-assessments.md) and [opportunity_card](../types/opportunity-card.md).

Validate every integer score in 1..5 and every source reference. For each requirement invoke the ordinary [dependency assessment](../types/dependency-assessment.md#term-dependency-assessment) module against the [frozen](../system/lifecycle.md#term-freeze) registry. Conflict and unknown are ineligible. Composite is the unweighted sum of novelty, feasibility and compute_alignment. Order all candidates by descending composite then ascending lexicographic sorted source idea_ids tuple. Preserve full rank, scores, evidence and rejection reasons, and select the first eligible row. Internal sort algorithm is unspecified.

No eligible candidate returns the typed helper failure NO_ELIGIBLE_OPPORTUNITY to the pinned Screening Python wrapper. It raises the declared cc.Failure; the handler records CAPSULE_ERROR with the no-winner diagnostic code and emits no output Artifact. Supervisor triage [halts](../system/lifecycle.md#term-halt) before Hypothesis. No model-generated card may replace that failure. Invalid assessment/schema/reference retains OUTPUT_INVALID diagnostics under ordinary [capsule](../capsule/capsule.md#term-capability-capsule) error; missing registry retains POLICY_UNRESOLVED diagnostics and prevents execution/advancement.

The PRD 4.4 required offline [RSI target](../capsule/rsi.md#term-rsi-target) is this helper's implementation. Candidate optimization may change code while preserving exact reference outputs, dependency policy and schemas. Protected [fixtures](../system/test-surfaces.md#term-fixture) and runtime [Tier 1](../verification.md#term-tier-1) [checks](../capsule/fields.md#term-check) remain independent. Candidate admission/activation creates a new Screening capsule version; it never modifies live code during a run. Conditional text [RSI](../rsi.md#term-rsi) is a separate target.

## Tests

Independent fixtures cover ordinary ranks, ties, filtered/unknown dependencies, invalid scores and no winner. This is a functional-core boundary following [Python sorted key functions](https://docs.python.org/3/howto/sorting.html#key-functions): the contract fixes order while allowing a replacement implementation.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.op-rank-opportunities.AC-01 | PRD 3.4.7 | Composite equals the unweighted sum of the three scores; order is composite descending then ascending sorted idea_ids tuple; fixtures with ties give the expected order. | BLOCK |
| cap.op-rank-opportunities.AC-02 | PRD 3.4.7 | A score outside 1..5 or an unresolved source reference is rejected with OUTPUT_INVALID diagnostics. | BLOCK |
| cap.op-rank-opportunities.AC-03 | PRD 3.4.6 | [Candidates](../schemas/candidate.md#term-candidate) with a conflict or unknown dependency are ineligible but keep full rank, scores and rejection reasons in the card. | BLOCK |
| cap.op-rank-opportunities.AC-04 | US-10 | When no candidate is eligible the helper returns NO_ELIGIBLE_OPPORTUNITY; no model card replaces it. | BOUNDARY |
| cap.op-rank-opportunities.AC-05 | N_node | A missing registry yields POLICY_UNRESOLVED diagnostics. | BOUNDARY |
| cap.op-rank-opportunities.AC-06 | US-13 | A candidate implementation reproduces the reference outputs exactly on the protected fixtures before it can be admitted. | SYSTEM |
