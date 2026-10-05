---
id: cap.intent-gate
type: gate-profile
level: detail
status: draft
version: 1
provides: [research.accept_intent]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-host.md, ../capsule/gate-capsules.md, intent-compile.md, README.md]
tags: [gate, profile, intent]
prd: [3.2.1, 4.2.1, 4.2.8, 4.7.1, 4.7.3]
---

# `research.accept_intent.v1`: the intent Gate profile

PRD: 3.2.1, 4.2.1, 4.2.8, 4.7.1, 4.7.3

> Answers: Which checks decide whether an IntentIR is accepted, and how is the verdict formed?

A pinned profile of the shared `research.verifier` CC. It is not a separate [capsule](../capsule/capsule.md#term-capability-capsule). It is used in two places:

1. As the **nested review call** inside [`research.compile_intent`](intent-compile.md)'s repair loop.
2. As the **[Gate](../verification.md#term-gate) `G_intent`** after the compile CC returns, in a fresh independent call. This second use decides advance or halt.

Both uses see the same inputs: the request (`source_text.text`) and the [IntentIR](../types/intent-ir.md#term-intentir). Both return a `verifier_assessment` with the six criteria below, each answered exactly once.

## Criteria

[Tier 1](../verification.md#term-tier-1) deterministic [checks](../capsule/fields.md#term-check), then the six [Tier 2](../verification.md#term-tier-2) criteria with their rubrics, follow.

## Tier 1 (deterministic, before any model call)

- Type checks of `intent_ir`: schema, unique ids, resolved references, well-formed spans.
- `source_spans_exact`: spans lie inside the request text.
- `generation_within_budget`.
- Call budgets: time, [model turns](../system/model-bridge.md#term-model-turn).

A Tier 1 failure fails the Gate without calling the verifier.

## Tier 2 criteria (model-judged)

All six are required, once each, in this order. Every `fail` or `unknown` needs at least one quote copied exactly from the request. Source spans are bound by code from the quotes, never taken from the model.

| Criterion | Pass when |
|---|---|
| `goals_supported_by_source` | every goal restates something the request says |
| `outcomes_supported_by_source` | every outcome is a deliverable the request asks for, with enumerated fields, sections, counts and statuses kept |
| `constraints_supported_by_source` | every constraint matches the request, and `constraint.expression` carries the same meaning as the statement (strict limits, ordering, conditions, approval before action, stop and halt triggers) |
| `no_material_omissions` | every request, "must" and "must not" in the text appears as a goal, outcome or constraint; a placeholder such as "the required fields" or "etc." does not replace details the request spelled out |
| `no_unrequested_execution` | nothing was added that the request did not ask for |
| `ambiguity_unknown_classification` | ambiguities, conflicts and unknowns are used correctly: facts discoverable later are not failures; unclear text is `unknown`, not guessed |

Rules for the reviewer prompt (carried over from the AI4Research reviewer):

- Report an error only when a deliverable, scope, constraint, authorization or meaning is changed or omitted. Awkward wording is a warning.
- Keep the request's strength: "target", "aim" and "prefer" are not hard bounds. Do not demand a cap unless the request says "must", "maximum" or "no more than".
- A qualitative property such as "concise" encoded as a literal expression is correct. Do not fail it for lacking a property check.
- An "only these values are allowed" list stays an exact literal.
- When a target comes with an explicit fallback for an unavailable case, both must stay visible.
- Do not report span-bound problems; code handles that.
- The reviewer judges. It never rewrites the IntentIR.

## Evidence the Gate host supplies

The `evidence_bundle` carries: subject (`research.compile_intent` declaration hash), the six criteria with these rubrics, inputs (`source_text`), outputs (`intent_ir`), and the [Observation](../schemas/observation.md#term-observation) refs of the compile call, so the trail of compile, review and repair turns is visible to the reviewer. The producer cannot choose the criteria; the plan pins this profile.

## Verdict handling

| Reviewer result | Gate |
|---|---|
| all pass | PASS |
| warnings only | PASS_WITH_KNOWN_LIMITATIONS |
| any criterion fails | FAIL (halt) |
| any criterion unknown, or malformed answer | INCONCLUSIVE (halt for review) |
| blocking ambiguity or conflict left in the IntentIR | FAIL with the questions listed. M1 has no interactive clarification: the run [halts](../system/lifecycle.md#term-halt) and a human reads the questions. |

## Tests

Planted defects: faithful IntentIR; constraint removed; goal invented; unrequested execution added; constraint expression that contradicts its statement; "target" turned into a hard cap; placeholder replacing enumerated fields. Reviewer answers that omit a criterion, repeat one, or quote text not in the request must block.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.intent-gate.AC-01 | G_intent | A Tier 1 failure (schema, unique ids, span bounds, budget) yields FAIL with 0 verifier calls. | BLOCK |
| cap.intent-gate.AC-02 | G_intent, US-03 | For each planted defect (constraint removed, goal invented, unrequested execution added, contradicting constraint expression, target turned into hard cap, placeholder replacing enumerated fields) the Verdict is FAIL and quotes the request text. | BLOCK |
| cap.intent-gate.AC-03 | G_intent | A faithful IntentIR gives PASS; warnings only gives PASS_WITH_KNOWN_LIMITATIONS; any unknown criterion or malformed answer gives INCONCLUSIVE and halts. | BLOCK |
| cap.intent-gate.AC-04 | G_intent | Reviewer answers that omit a criterion, repeat one, or quote text not in the request block the Gate; all six criteria appear exactly once, in order. | BLOCK |
| cap.intent-gate.AC-05 | G_intent, US-03 | After a failed intent Gate, 0 requirement calls start and the halt report names the failed criterion and the request quote. | BOUNDARY |
| cap.intent-gate.AC-06 | G_intent | The Gate verdict is committed as a [Verification](../schemas/verification-record.md#term-verification) before any release record; a failed save [releases](../system/lifecycle.md#term-release) nothing. | BOUNDARY |
| cap.intent-gate.AC-07 | N_intent, G_intent | The nested review inside the compile CC and the Gate review are separate calls with separate Observations. | SYSTEM |
