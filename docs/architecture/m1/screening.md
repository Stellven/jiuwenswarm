---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../types/idea-set.md, ../types/research-brief.md, ../types/screening-assessments.md, ../types/opportunity-card.md, op-rank-opportunities.md, ../capsule/runner.md]
provides: [research.select_opportunity]
consumes: [cc.type.idea_set, cc.type.research_brief, cc.type.screening_assessments, cc.type.opportunity_card, op.rank_opportunities]
depends_on: [../types/idea-set.md, ../types/research-brief.md, ../types/screening-assessments.md, ../types/opportunity-card.md, op-rank-opportunities.md, screening-gate.md, pipeline.md]
tags: [m1, capsule, screening]
---

> **Draft coding-handoff contract.** This page owns Screening. Decisions 48–53 use sourced, replaceable defaults recorded in the [decision ledger](../decisions.md); no missing product prose remains a black-box blocker.

# `research.select_opportunity`: Screening (PRD 3.4)

## Responsibility and boundary

Screening consolidates the `idea_set`, assesses every consolidated candidate against the Research Brief, asks the deterministic ranking operator to apply the dependency filter and ordering, and emits exactly one [`opportunity_card`](../types/opportunity-card.md). It does not search for new evidence or change intake, repository, or dataset state. Its capability name is independent of the M1 stage that currently calls it, following the reusable typed-component style of [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/).

The main-path ports are `idea_set` and `research_brief` in, and `opportunity_card` out. The capsule's internal typed handoff to [`op.rank_opportunities`](op-rank-opportunities.md) is `screening_assessments`; that value is not a pipeline Artifact. The producer of `idea_set`, this capsule, the helper, and the consumer at Hypothesis all use the one canonical page for each type.

## Contract

| Port / effect | Contract |
|---|---|
| Input `idea_set` | Required `cc.type.idea_set`, produced by `research.search_ideas`; every idea must be represented exactly once in the consolidated candidate groups. |
| Input `research_brief` | Required `cc.type.research_brief`, produced by `research.compile_brief`; supplies the objective, scope, and compute constraints used for relevance and scoring. |
| Nested call input `assessments` | Required `cc.type.screening_assessments` on the helper's `assessments` port; contains consolidated candidate content, evidence references, dependencies, scores, and justifications. Its idea, citation, and chunk references must resolve to the two capsule inputs. |
| Nested call output `opportunity_card` | Required `cc.type.opportunity_card`; contains the selected card and one ordered score/disposition row per consolidated candidate. |
| Main output `opportunity_card` | Required `cc.type.opportunity_card`; emitted only after the helper succeeds. Hypothesis consumes this exact named type. |
| Effects | `read_only`, `reads_external`; no direct network access, filesystem writes, or user interaction. The helper is pure. |
| Failure | If all candidates are filtered, propagate `NO_ELIGIBLE_OPPORTUNITY`; emit no output Artifact and halt before Hypothesis. Other nested-call runtime failures retain their runtime reason and halt/resume behavior. |

The [`opportunity_card`](../types/opportunity-card.md) page defines the complete output shape and deterministic type checks. [`screening_assessments`](../types/screening-assessments.md) defines the private helper input. No second schema is defined here.

## PRD 3.4 behavior promised at the boundary

1. Make one bounded, single-pass consolidation of the at-most-three input ideas, retaining every source idea id and material difference; preserve variants that rely on different mechanisms or baseline papers. Each input idea occurs in exactly one consolidated candidate. Do not iteratively cluster or re-index sources.
2. Form a candidate card from the input ideas and their cited evidence. Preserve all source and chunk references. The candidate carries the PRD 3.4.3/3.4.4 content: title, summary, problem, mechanism, opportunity, relevance, assumptions, evidence maturity, verification path, uncertainties, risks, and open questions.
3. In one bounded LLM turn over the full consolidated candidate set, assess each candidate against exactly the PRD's fixed 1–5 dimensions `novelty`, `feasibility`, and `compute_alignment`, with an evidence-grounded one-sentence justification for each. `evidence_maturity` and `verification_path` are required qualitative fields and do not add hidden numeric weights. Novelty compares the candidate to the Brief's cited evidence and the cited Idea evidence. There is no follow-up debate, vote, or live feasibility execution.
4. Declare package, model and dataset dependencies with canonical registry identifiers. The pure helper assesses each against the frozen registry. Only `compatible` dependencies remain eligible; `conflict` and `unknown` are ineligible. User value, timing, safety, licensing exposure and resource implications remain visible context in the card and rationale; only the dependency assessment changes M1 eligibility.
5. Call `op.rank_opportunities` once as `cc.call("op.rank_opportunities", assessments=<screening_assessments value>)`. It sums the three scores without weights, orders by composite descending and then the ascending lexicographic tuple of sorted source `idea_ids`, and selects the first eligible candidate. Sorting implementation is unspecified.
6. Run deterministic type/provenance checks and the Screening gate. Only an accepted output reaches Hypothesis.

## Declaration (`capsule.json`)

This capsule is `kind: skill`: the bounded prompt is its implementation and it makes one typed call to the pinned pure operator. RSI may propose changes only to `SKILL.md` and its owned assessment rubric. Deterministic provenance checks, ranking, dependency policy, schemas and Gate rubrics are separate non-RSI dependencies.

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "research.select_opportunity",
    "kind": "skill",
    "body": [
      {"path": "SKILL.md", "sha256": "<author kit>"},
      {"path": "rubrics/assess_opportunities.md", "sha256": "<author kit>"}
    ],
    "summary": "Consolidate searched ideas, form evidence-linked opportunity assessments against the Research Brief, and return the top eligible opportunity with a complete deterministic ranking record."
  },
  "ports": {
    "inputs": [
      {"name": "idea_set", "type": "idea_set", "required": true, "description": "The searched candidate ideas and the evidence passages and sources they cite."},
      {"name": "research_brief", "type": "research_brief", "required": true, "description": "The objective, scope, and constraints candidates must answer."}
    ],
    "outputs": [
      {"name": "opportunity_card", "type": "opportunity_card", "check_id": "screening_provenance", "description": "The selected opportunity and the ordered score and eligibility record for every consolidated candidate."}
    ]
  },
  "needs": {
    "when": [],
    "external": [
      {"ref": "op.rank_opportunities", "decl_hash": "<admitted>", "purpose": "apply the pinned dependency-conflict filter, score sum, deterministic order, and Top-1 selection"}
    ],
    "network": "none",
    "human_interaction": "none",
    "resources": {"timeout_s": 600}
  },
  "changes": {"effect_class": "read_only", "effects": [], "state_kind": "reads_external"},
  "guarantees": {
    "checks": [
      {"id": "screening_provenance", "anchor": "deterministic", "target": "ports.outputs.opportunity_card", "over": "inputs_and_outputs", "applies_at": "both", "runner": {"ref": "checks/screening_checks.py:provenance_is_complete", "sha256": "<author kit>"}, "description": "Every input idea occurs in exactly one consolidated candidate; every output idea id, citation and chunk reference resolves to the idea_set; score rows cover the consolidated groups exactly once; and the selected card equals the first eligible row.", "author": "muk"},
      {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.opportunity_card", "over": "inputs_and_outputs", "applies_at": "admission", "runner": {"ref": "checks/screening_checks.py:matches_reference", "sha256": "<author kit>"}, "description": "On each fixture, the consolidated assessments and final opportunity card match the expected reference values.", "author": "muk"}
    ],
    "failure_modes": [
      {"reason_code": "NO_ELIGIBLE_OPPORTUNITY", "when": "The pinned ranking helper finds that every consolidated candidate conflicts with the dependency registry.", "retriable": false}
    ]
  },
  "evolution": {"rsi": "propose", "may_change": ["files:SKILL.md", "files:rubrics/assess_opportunities.md"], "notes": "Deterministic provenance, helper wiring, arithmetic, dependency policy, output schema and Gate rubrics are not mutation targets."}
}
```

## Gate and failure semantics

The step gate is [`research.accept_card`](screening-gate.md), following the [gate capsule pattern](../capsule/gate-capsules.md). Tier 1 validates type, score arithmetic, ordering, dependency decisions and provenance. Tier 2 assesses that candidates answer the Brief, use its evidence fairly, and that the selected card truthfully represents its source ideas. The Gate profile pins both sets.

`NO_ELIGIBLE_OPPORTUNITY` is a declared capsule failure, not an empty successful result. There is no `opportunity_card` artifact to judge or pass to Hypothesis. A malformed assessment, unresolved reference, or model reply that cannot be parsed is a capsule error. A nested call's runtime-owned failure is propagated with its original reason.

## Readiness

This is a connected draft for independent implementation. Remaining work is executable schema generation, examples, contract canaries and source-aware review. The dependency registry is replaceable through its pinned policy artifact; changing its contents creates a new hash, while changing assessment semantics creates a new operator/profile version.
