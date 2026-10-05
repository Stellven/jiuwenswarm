---
id: cap.screening-gate
type: gate-profile
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_card]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-host.md, README.md]
tags: [m1, gate, profile]
level: detail
prd: [3.4.5, 3.4.7, 4.2.1, 4.2.8]
---

# research.accept_card.v1 Gate profile

PRD: 3.4.5, 3.4.7, 4.2.1, 4.2.8

> Answers: Which checks decide whether the selected opportunity card is accepted?

This is a pinned profile for the shared `research.verifier`, not a separate [capsule kind](../capsule/capsule.md#term-capsule-kind). The selected card is grounded in linked ideas/evidence and answers the [Brief](../types/research-brief.md#term-research-brief) with credible verification and compute constraints. [Tier 1](../verification.md#term-tier-1) independently recomputes dependency eligibility, composite score, stable tie break and preserved rejection reasons.

The owning [Gate host](../capsule/gate-host.md) evaluates `evaluate(evidence_bundle_ref, gate_profile_ref, request_id) -> verification_ref`. The [frozen](../system/lifecycle.md#term-freeze) bound plan sets `gate_capsule_name: research.verifier` and this profile's immutable reference. Referee rubrics are trusted profile assets with exact hashes, independently authored from work-capsule prompts and excluded from [RSI](../rsi.md#term-rsi) mutation. Missing/unknown evidence [halts](../system/lifecycle.md#term-halt); failed persistence cannot release the next step. Output is a durable [Verification](../schemas/verification-record.md#term-verification), while the verifier itself returns [verifier_assessment](../types/verifier-assessment.md#term-verifier-assessment).

## Criteria

Tier 1 [checks](../capsule/fields.md#term-check) are in the paragraph above. The two judged criteria and their rubrics follow.

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
name: research.verifier
---
You judge the selected research opportunity and its supporting evidence. The INPUT block contains
the Brief, idea set, opportunity card, and criteria. Follow the judging instructions and each
criterion's rubric. Assess; do not change the candidate ranking or decide the gate outcome.
```

## Tests and open decisions

Tests follow the shared pattern: one case per pattern check, with recorded judge replies and expected assessments. Include a grounded card, an unsupported claim, an out-of-scope opportunity, and insufficient evidence (`unknown`). These [fixtures](../system/test-surfaces.md#term-fixture) validate the gate contract, not live judge calibration.

The gate's assessment shape and deterministic fold behavior come from the shared CC [Gate](../verification.md#term-gate) contract. Its pinned profile requires type/provenance/ranking/dependency checks plus the two semantic criteria above. The shared Gate and [Capability Capsule](../capsule/capsule.md#term-capability-capsule) contract lives in the capsule pages; a rubric revision creates a new rubric/profile hash and reopens Screening evidence without changing the Gate API.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.screening-gate.AC-01 | G_node | A grounded card gives PASS on card_grounded and card_answers_brief with recorded replies. | BLOCK |
| cap.screening-gate.AC-02 | G_node | A card with an unsupported claim or overstated evidence maturity gives FAIL on card_grounded. | BLOCK |
| cap.screening-gate.AC-03 | G_node | An out-of-scope opportunity gives FAIL on card_answers_brief; insufficient evidence gives unknown and INCONCLUSIVE. | BLOCK |
| cap.screening-gate.AC-04 | G_node | Tier 1 independently recomputes dependency eligibility, composite score, tie break and preserved rejection reasons; any difference from the card yields FAIL with 0 verifier calls. | BLOCK |
| cap.screening-gate.AC-05 | US-07 | After a failed card Gate, 0 hypothesis calls start. | SYSTEM |
| cap.screening-gate.AC-06 | G_node | The Gate does not change the candidate ranking or the selected card. | BOUNDARY |
