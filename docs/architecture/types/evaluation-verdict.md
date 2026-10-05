---
type: payload-type
id: cc.type.evaluation_verdict
version: 2
status: draft
tags: [types, m1]
prd: [3.8.5, 3.8.4, 3.5.4]
level: detail
---

# `evaluation_verdict`: the scientific outcome · version 2

PRD: 3.8.5, 3.8.4, 3.5.4

The [frozen](../system/lifecycle.md#term-freeze) PRD 3.8 scientific classification and its supporting comparisons. PRD 3.5.4 requires pre-registered [boundaries](../system/modules.md#term-boundary) and defaults the middle zone to INCONCLUSIVE. Infrastructure errors are recorded separately and cannot masquerade as scientific rejection.

A scientific fail is a valid research result. The [Gate](../verification.md#term-gate) verifies correct evaluation, including recomputation of the approved mapping; it never requires scientific success. It may check the classification for consistency without substituting its own interpretation.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-evaluation-verdict"></a>**evaluation_verdict** (also: evaluation verdict) | The scientific classification of the results, with its supporting comparisons. A middle-zone result defaults to INCONCLUSIVE, and infrastructure errors are recorded separately and never pass as scientific rejection. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `classification` | `enum(PASS, FAIL, INCONCLUSIVE, CONDITIONALLY_ACCEPTABLE)` | req | checked |  | Scientific label, distinct from Gate verdict; applies frozen Blueprint middle-zone rule |
| `comparisons` | `list<object>` | req | checked |  | At least one. One entry per frozen metric |
| `comparisons[].metric_id` | `id` | req | checked |  | Blueprint metric ID |
| `comparisons[].measured` | `number?` | req | checked |  | Transformed value in the frozen comparison basis; null if not computable |
| `comparisons[].claim_met` | `boolean?` | req | checked |  | Frozen expected predicate; null if unavailable |
| `comparisons[].acceptance_met` | `boolean?` | req | checked |  | Frozen [Brief](research-brief.md#term-research-brief) acceptance predicate; null if absent or unavailable |
| `comparisons[].falsified` | `boolean?` | req | checked |  | Frozen falsification predicate; null if unavailable |
| `comparisons[].outcome` | `enum(met, between, falsified, unmeasured)` | req | checked |  | Convenience projection checked against these predicates |
| `evidence_complete` | `boolean` | req | checked |  | All declared metrics have traceable complete samples |
| `plausibility` | `object` | req | checked |  | Exactly one model model [turn](../system/model-bridge.md#term-model-turn) for qualitative physical/experimental sanity review |
| `plausibility.plausible` | `boolean` | req | checked |  | False flags an execution/validity anomaly |
| `plausibility.rationale` | `text` | req | checked |  | Grounded in admitted evidence, no new external fetch |
| `residual_risks` | `list<text>` | req | checked |  | Untested conditions and guards; may be empty |
| `follow_ups` | `list<text>` | req | checked |  | Recommendations only, never an automatic rerun |
| `ext` | `map<string, json>` | opt | checked |  | Producer extensions; consumers ignore |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | Generated schema matches |
| `evaluation_contract` | deterministic | `outputs` | `both` | `cc/checks/registry/research.py:evaluation_contract` | cc-team | Metric coverage and transformations recompute from frozen inputs; predicate booleans match; classification matches approved policy, including guards/missing data/anomalies; no benchmark rerun or changed thresholds |

## Example

```json
{
  "classification": "INCONCLUSIVE",
  "comparisons": [
    {
      "metric_id": "M1",
      "measured": 35,
      "claim_met": false,
      "acceptance_met": true,
      "falsified": false,
      "outcome": "between"
    }
  ],
  "evidence_complete": true,
  "plausibility": {
    "plausible": true,
    "rationale": "The measured values are nonnegative and imply a 35% reduction."
  },
  "residual_risks": [
    "Tested at batch size 1 only."
  ],
  "follow_ups": [
    "Consider a separately approved run at another batch size."
  ]
}
```

The example lies between success 40 and falsification 10 and uses the Blueprint default INCONCLUSIVE. Passing Brief acceptance 30 cannot silently convert it to CONDITIONALLY_ACCEPTABLE.

Classification order: unavailable/nonfinite comparisons, incomplete evidence or implausibility produce INCONCLUSIVE with explicit validity blockers and an infrastructure evidence check; falsified goals or failed guards on admissible evidence produce FAIL; all goal claims, guards and mandatory Brief acceptance passing produce PASS; remaining admissible evidence uses the preregistered middle-zone rule. CONDITIONALLY_ACCEPTABLE additionally requires every mandatory Brief acceptance and guard predicate passing. A label never authorizes advancement: the infrastructure Gate rejects missing mandatory evidence regardless of an INCONCLUSIVE payload. The evaluator cannot create an ERROR scientific tag, shift boundaries or rerun experiments.
