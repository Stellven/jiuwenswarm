---
type: payload-type
id: cc.type.verifier_assessment
version: 1
status: checked
tags: [types, m1, verifier]
---

> **Checked, not yet approved.** Compiles, its example validates, and it has been through review.

# `verifier_assessment`: the judge's answer · version 1

The judge's result for each criterion of an [`evidence_bundle`](evidence-bundle.md). The judge **assesses**; it never decides. The gate (M10) folds these results with Tier 1's and writes the [Verification](../schemas/verification-record.md).

**Made by** the step's gate capsule, which the Binding names in `verifier` ([nodes](../system/nodes.md#gates)). Admission's own judge is the policy's `levels.admission_judge`. **Read by** the gate host (M10), which turns each criterion into one `results[]` entry of the Verification ([gate host](../capsule/gate-host.md#what-it-does-in-order), step 6).

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `criteria` | `list<object>` | req | checked |  | At least one. One entry per criterion of the bundle, in the same order |
| `criteria[].check_id` | `id` | req | checked |  | The bundle's `check_id` it answers |
| `criteria[].result` | `enum(pass, fail, unknown)` | req | checked |  | `unknown` when the judge cannot tell from what it was shown; never counted as a pass (INV-8) |
| `criteria[].rationale` | `text` | req | checked |  | Why, in a few sentences, citing the rubric |
| `criteria[].quotes` | `list<text>` | req | checked |  | Short verbatim quotes from the bundle's `inputs` or `outputs` that the rationale rests on. May be empty only for `unknown` |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer |

**How the gate host reads it:** see [the gate host](../capsule/gate-host.md#what-it-does-in-order), step 4.

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |

Checks that need the bundle, such as whether every criterion is answered and every quote is real, belong to the producer: every gate capsule carries them ([gate capsules](../capsule/gate-capsules.md#the-three-checks-every-gate-capsule-carries)). A gate call gets no Verification, so the gate host runs the type check and those checks itself before folding; a fail makes every criterion `unknown`, and the step `blocked` (INV-8).

## Example

```json
{"criteria": [{"check_id": "intent_fidelity", "result": "fail",
  "rationale": "The prompt asks for a comparison that covers both bit widths, but the IntentIR has no goal or constraint for it.",
  "quotes": ["Compare 4-bit and 8-bit quantisation", "\"constraints\": []"]}]}
```
