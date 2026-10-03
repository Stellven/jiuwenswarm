---
type: design
status: draft
version: 3
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [op.rank_opportunities]
consumes: [cc.type.screening_assessments, cc.type.opportunity_card]
depends_on: [screening.md, op-assess-dependency.md]
tags: [m1, module, ranking]
---

# Ordinary rank_opportunities helper

Local pure callable `rank_opportunities(assessments, dependency_registry_ref) -> opportunity_card` lives with the Screening implementation, pinned by its body hash. It is not a separately admitted capability. Input/output field owners are [screening_assessments](../types/screening-assessments.md) and [opportunity_card](../types/opportunity-card.md).

Validate every integer score in 1..5 and every source reference. For each requirement invoke the ordinary dependency assessment module against the frozen registry. Conflict and unknown are ineligible. Composite is the unweighted sum of novelty, feasibility and compute_alignment. Order all candidates by descending composite then ascending lexicographic sorted source idea_ids tuple. Preserve full rank, scores, evidence and rejection reasons, and select the first eligible row. Internal sort algorithm is unspecified.

No eligible candidate returns the typed helper failure NO_ELIGIBLE_OPPORTUNITY to the trusted skill wrapper. The wrapper emits no output Artifact, records triage and halts before Hypothesis. No model-generated card may replace that failure. Invalid assessment/schema/reference returns OUTPUT_INVALID; missing registry returns POLICY_UNRESOLVED.

The PRD 4.4 required offline RSI target is this helper's implementation. Candidate optimization may change code while preserving exact reference outputs, dependency policy and schemas. Protected fixtures and runtime Tier 1 checks remain independent. Candidate admission/activation creates a new Screening owner version; it never modifies live code during a run. Conditional text RSI is a separate target.

Independent fixtures cover ordinary ranks, ties, filtered/unknown dependencies, invalid scores and no winner. This is a functional-core boundary following [Python sorted key functions](https://docs.python.org/3/howto/sorting.html#key-functions): the contract fixes order while allowing a replacement implementation.
