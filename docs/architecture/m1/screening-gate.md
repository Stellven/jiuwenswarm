---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, screening.md, ../capsule/gate-capsules.md]
provides: [research.accept_card]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment, cc.type.opportunity_card, cc.gate_capsule_pattern]
depends_on: [../capsule/gate-capsules.md, screening.md, pipeline.md]
tags: [m1, gate, capsule, screening]
---

> **Draft coding-handoff contract.** Follows the shared Gate API and pins the Screening Gate profile.

# `research.accept_card`: Screening gate

## What it checks

The gate assesses the accepted `opportunity_card` against the two Screening criteria recorded in the run plan:

- **`card_grounded`:** selected card claims, mechanism, assumptions, and evidence maturity are supported by the linked idea text and evidence chunks. The maturity description must accurately characterize the evidence rather than inflate it.
- **`card_answers_brief`:** the selected opportunity addresses the Research Brief objective and respects its scope and compute constraints; its verification path is credible against the supplied values and can test the proposed mechanism.

Deterministic Tier 1 checks validate the named type, complete score/rank invariants, and references back to the `idea_set`. The judge assesses only the named criteria and cannot change ranking or eligibility; the shared gate host applies its fold policy to route the result.

## Run-plan entry

Step `screening` on [the M1 pipeline](pipeline.md), gate `research.accept_card`; criterion checks and rubric references appear in [the recorded plan](pipeline.md#the-plan-as-recorded).

## Declaration (`capsule.json`)

As [the shared gate pattern](../capsule/gate-capsules.md), with these values:

| Field | Value |
|---|---|
| `identity.name` | `research.accept_card` |
| `identity.body` | `SKILL.md`, `rubrics/card_grounded.md`, `rubrics/card_answers_brief.md` |
| `identity.summary` | Assess whether the selected opportunity is grounded in its cited ideas and evidence, and answers the Research Brief under its scope and constraints; return an assessment for each criterion with rationale and verbatim quotes. |
| `ports.inputs[0].description` | The opportunity card, Brief, idea set, and criteria to judge. |

These two qualitative judgments cover evidence maturity and verification credibility as PRD 3.4.5 requests. They do not add score dimensions or alter deterministic ranking.

## `rubrics/card_grounded.md` (provisional)

```text
Criterion: card_grounded.

Use the idea_set and opportunity_card in the evidence bundle. Check the selected card's title,
summary, problem, mechanism, assumptions, evidence maturity, and verification path against the
represented idea text and linked evidence chunks.

Pass when material claims are supported by the cited ideas or chunks, the evidence_maturity field
accurately describes the evidence shown, and the card preserves material uncertainty rather than
presenting it as established fact. Fail when it adds an unsupported claim, overstates evidence
maturity, misstates its sources, or hides a material uncertainty. Unknown when the supplied evidence
is not enough to decide.
```

## `rubrics/card_answers_brief.md` (provisional)

```text
Criterion: card_answers_brief.

The Research Brief is the research_brief in the bundle's inputs.

Pass when the opportunity advances the Brief's objective, stays within its scope, respects the stated
constraints, and gives a verification_path that is credible with the supplied baseline, dataset, and
framework constraints and can test the proposed mechanism. Fail when it answers a different problem,
depends on an excluded resource, violates a constraint, or offers no credible way to test the
mechanism. Unknown when the Brief or card lacks enough information.
```

## `SKILL.md` (provisional)

```text
---
name: research.accept_card
---
You judge the selected research opportunity and its supporting evidence. The INPUT block contains
the Brief, idea set, opportunity card, and criteria. Follow the judging instructions and each
criterion's rubric. Assess; do not change the candidate ranking or decide the gate outcome.
```

## Tests and open decisions

Tests follow the shared pattern: one case per pattern check, with recorded judge replies and expected assessments. Include a grounded card, an unsupported claim, an out-of-scope opportunity, and insufficient evidence (`unknown`). These fixtures validate the gate contract, not live judge calibration.

The gate's assessment shape and deterministic fold behavior come from the shared CC Gate contract. Its pinned profile requires type/provenance/ranking/dependency checks plus the two semantic criteria above. Muk owns the shared Gate and Capability Capsule contract; a rubric revision creates a new rubric/profile hash and reopens Screening evidence without changing the Gate API.
