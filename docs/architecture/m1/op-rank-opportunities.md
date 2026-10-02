---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../types/screening-assessments.md, ../types/opportunity-card.md, ../capsule/runner.md]
provides: [op.rank_opportunities]
consumes: [cc.type.screening_assessments, cc.type.opportunity_card, op.assess_dependency]
depends_on: [../types/screening-assessments.md, ../types/opportunity-card.md, ../capsule/runner.md, op-assess-dependency.md]
tags: [m1, operator, capsule, screening]
---

> **Draft coding-handoff contract.** The pure deterministic helper called by Screening. CC policy owns the frozen dependency registry; this operator owns assessment and ordering semantics.

# `op.rank_opportunities`: filter and rank assessed candidates

## What it does

Given the screening skill's assessments, it checks declared package, model and dataset dependencies against its pinned registry, computes each composite as the sum of the three scores, orders every candidate, and returns one `opportunity_card` containing the first eligible candidate and the complete ordered score/disposition record. It does not call a model, use the network, or change state.

## Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "op.rank_opportunities",
    "kind": "tool",
    "body": [
      {"path": "rank_opportunities.py", "sha256": "<author kit>"}
    ],
    "summary": "Filter assessed opportunities against the pinned dependency-conflict registry, calculate their composite scores, order them deterministically, and return the top eligible opportunity with screening dispositions."
  },
  "ports": {
    "inputs": [
      {"name": "assessments", "type": "screening_assessments", "required": true,
       "description": "Structured cards and scores for each consolidated candidate."}
    ],
    "outputs": [
      {"name": "opportunity_card", "type": "opportunity_card", "check_id": "ranking_is_consistent",
       "description": "The selected eligible card and all candidate scores and dispositions in deterministic order."}
    ]
  },
  "ext": {"runner": {"failure_code": "NO_ELIGIBLE_OPPORTUNITY"}},
  "needs": {
    "when": [], "external": [{"ref": "op.assess_dependency", "decl_hash": "<admitted>", "purpose": "map each declared dependency through the frozen registry"}], "network": "none", "human_interaction": "none",
    "resources": {"timeout_s": 10}
  },
  "changes": {"effect_class": "pure", "effects": [], "state_kind": "none"},
  "guarantees": {"checks": [
    {"id": "ranking_is_consistent", "anchor": "deterministic", "target": "ports.outputs.opportunity_card",
     "over": "inputs_and_outputs", "applies_at": "both",
     "runner": {"ref": "checks/ranking_checks.py:ranking_is_consistent", "sha256": "<author kit>"},
     "description": "The output covers each input candidate exactly once; every composite is the sum of its three scores; the order is descending composite then ascending lexicographic idea-id tuple; the selected card is the first eligible candidate; every ineligible candidate records its matched conflict.",
     "author": "muk"},
    {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.opportunity_card",
     "over": "inputs_and_outputs", "applies_at": "admission",
     "runner": {"ref": "checks/ranking_checks.py:matches_reference", "sha256": "<author kit>"},
     "description": "For each test case, the output scores, dispositions, order, and winner equal the expected reference result.",
     "author": "muk"}
  ], "failure_modes": [
    {"reason_code": "NO_ELIGIBLE_OPPORTUNITY", "when": "Every candidate is excluded by the pinned dependency-conflict registry.", "retriable": false}
  ]},
  "evolution": {"rsi": "none"}
}
```

## Contract

- The composite is the sum of `novelty`, `feasibility`, and `compute_alignment` (PRD 3.4.7).
- Order every candidate by composite descending, then by the sorted `idea_ids` tuple lexicographically ascending; input order never decides a tie.
- For each requirement, call pinned [`op.assess_dependency`](op-assess-dependency.md). Both `conflict` and `unknown` make the candidate ineligible; the complete returned assessments are preserved.
- Keep ineligible candidates in the ordered scores with `eligible: false`, complete dependency assessments, and a rejection rationale. They cannot be selected.
- Select the first eligible candidate in that order. The returned `scores` array preserves the entire order and uses one-based consecutive ranks.
- If no candidate is eligible, raise declared failure `NO_ELIGIBLE_OPPORTUNITY`; return no output value or `opportunity_card` Artifact. The run halts at Screening, records human triage, and Hypothesis does not start. Because no output exists, no Screening Gate call is made.
- The registry is part of the operator's pinned body, so its contents are fixed by `decl_hash` for a run. CC policy owns publication. New facts create a new registry hash; changed comparison semantics require a new operator/profile version.

The implementation may use any sorting method that produces this exact output order.

## Runs and tests

As a nested call, this operator has no separate step gate. The parent Screening capsule carries the registry and input-aware checks for the complete output; the operator's deterministic and reference checks run at admission. Fixtures cover a normal ranked result, a score tie, one filtered candidate, and no eligible candidate.

## Replacement boundary

The registry may move to another local provider if it returns the same `dependency_assessment` values for the pinned registry hash. Ranking implementation may change freely if the observable order and failure behavior remain identical.
