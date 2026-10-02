---
type: payload-type
id: cc.type.research_brief
version: 1
status: checked
tags: [types, m1]
---

> **Checked, not yet approved.** Compiles, its example validates, and it has been through review.

# `research_brief`: the Research Brief · version 1

The contract every later stage reads: the research objective, its scope, the constraints, the prioritised requirements and the acceptance metrics (PRD 3.2.7). Every item the user stated carries a quote and names where the quote came from, so a check can confirm the user really said it. Anything the user did not state is either a recorded default or absent.

**Made by** `research.compile_brief` at the `requirement` step ([requirement capsule](../m1/requirement-capsule.md)). **Read by** every later step: search (3.2.2 scope), hypothesis (3.5 copies its metrics), benchmarking and evaluation (3.2.6 thresholds), and the report.

**Evidence.** An `evidence` quote is copied verbatim from its source. `evidence_source_id` names the source: `prompt` for `intake.prompt`, or a `documents[].document_id` of the same `intake`. Requirements, metrics and the objective quote the prompt: a document can inform the Brief, but only the user states what is required.

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `objective` | `text` | req | checked |  | The core research objective in one or two sentences, with no chosen solution (3.2.1) |
| `objective_evidence` | `text` | req | checked |  | A quote from the prompt that supports the objective |
| `in_scope_items` | `list<object>` | req | checked |  | What the research covers, taken only from the intake (3.2.2). May be empty |
| `in_scope_items[].item` | `text` | req | checked |  | One inclusion, in words |
| `in_scope_items[].evidence` | `text` | req | checked |  | The quote, copied verbatim from its source |
| `in_scope_items[].evidence_source_id` | `id` | req | checked |  | `prompt` or a `document_id` |
| `out_of_scope_items` | `list<object>` | req | checked |  | What it must not cover (3.2.2). May be empty |
| `out_of_scope_items[].item` | `text` | req | checked |  | One exclusion, in words |
| `out_of_scope_items[].evidence` | `text` | req | checked |  | The quote, copied verbatim from its source |
| `out_of_scope_items[].evidence_source_id` | `id` | req | checked |  | `prompt` or a `document_id` |
| `constraints` | `object` | req | checked |  | Every stated limit (3.2.4) |
| `constraints.compute` | `object` | req | checked |  | Compute limits. Each field present is either quoted in `constraints.compute.quotes` or listed in `defaults_applied`, never both |
| `constraints.compute.hardware` | `string` | req | checked |  | The hardware target. Example: `single_gpu`. Open: a fixed list of values ([open issues](../open-issues.md)) |
| `constraints.compute.gpu_memory_gb` | `number` | opt | checked |  | Stated GPU memory limit, in GB |
| `constraints.compute.runtime_limit_s` | `integer` | opt | checked |  | Stated runtime limit for one benchmark run, in seconds |
| `constraints.compute.token_budget` | `integer` | opt | checked |  | Stated model token budget. Recorded, not gated, at M1 |
| `constraints.compute.quotes` | `list<object>` | req | checked |  | One quote per compute field the user stated. May be empty |
| `constraints.compute.quotes[].field` | `enum(hardware, gpu_memory_gb, runtime_limit_s, token_budget)` | req | checked |  | Which compute field the quote supports |
| `constraints.compute.quotes[].evidence` | `text` | req | checked |  | The quote, copied verbatim from its source |
| `constraints.compute.quotes[].evidence_source_id` | `id` | req | checked |  | `prompt` or a `document_id` |
| `constraints.frameworks` | `list<object>` | req | checked |  | Stated framework or library requirements, such as PyTorch or a CUDA version. 3.6.1 builds `requirements.txt` from them. May be empty |
| `constraints.frameworks[].item` | `text` | req | checked |  | One requirement, in words |
| `constraints.frameworks[].evidence` | `text` | req | checked |  | The quote, copied verbatim from its source |
| `constraints.frameworks[].evidence_source_id` | `id` | req | checked |  | `prompt` or a `document_id` |
| `constraints.other_limits` | `list<object>` | req | checked |  | Any other stated limit: data, time, tools, policy. May be empty |
| `constraints.other_limits[].item` | `text` | req | checked |  | One limit, in words |
| `constraints.other_limits[].evidence` | `text` | req | checked |  | The quote, copied verbatim from its source |
| `constraints.other_limits[].evidence_source_id` | `id` | req | checked |  | `prompt` or a `document_id` |
| `mandatory_requirements` | `list<object>` | req | checked |  | At least one. What must be met (3.2.5) |
| `mandatory_requirements[].requirement_id` | `id` | req | checked |  | Unique among all requirements. Example: `R1` |
| `mandatory_requirements[].statement` | `text` | req | checked |  | The requirement, in words |
| `mandatory_requirements[].evidence` | `text` | req | checked |  | Its quote, from the prompt |
| `mandatory_requirements[].evidence_source_id` | `id` | req | checked |  | `prompt`; the producer's check `brief_evidence_grounded` enforces it |
| `optional_preferences` | `list<object>` | req | checked |  | What would be good to have (3.2.5). May be empty |
| `optional_preferences[].requirement_id` | `id` | req | checked |  | Unique among all requirements. Example: `P1` |
| `optional_preferences[].statement` | `text` | req | checked |  | The preference, in words |
| `optional_preferences[].evidence` | `text` | req | checked |  | Its quote, from the prompt |
| `optional_preferences[].evidence_source_id` | `id` | req | checked |  | `prompt`; the producer's check `brief_evidence_grounded` enforces it |
| `metrics` | `list<object>` | req | checked |  | Acceptance metrics (3.2.6), each making one requirement measurable. May be empty only when every mandatory requirement is qualitative, and the output's `issues` then has an `INPUT_INCOMPLETE` saying why |
| `metrics[].metric_id` | `id` | req | checked |  | Unique among metrics. Example: `M1` |
| `metrics[].requirement_id` | `id` | req | checked |  | The requirement it measures |
| `metrics[].name` | `string` | req | checked |  | A short snake_case name. Example: `vram_reduction` |
| `metrics[].comparator` | `enum(gte, lte)` | req | checked |  | `gte`: at least the target is good. `lte`: at most the target is good. The names match the `predicate_op` registry |
| `metrics[].target` | `number` | req | checked |  | The threshold. The number appears in the metric's own quote |
| `metrics[].unit` | `string` | req | checked |  | Example: `percent`. Open: whether `percent` means points or a relative change ([open issues](../open-issues.md)) |
| `metrics[].evidence` | `text` | req | checked |  | Its quote, from the prompt |
| `metrics[].evidence_source_id` | `id` | req | checked |  | `prompt`; the producer's check `brief_evidence_grounded` enforces it |
| `defaults_applied` | `list<object>` | req | checked |  | Every value taken from the defaults table because the intake said nothing (3.2.3). May be empty |
| `defaults_applied[].field` | `string` | req | checked |  | The dotted path of the defaulted field. Example: `constraints.compute.hardware` |
| `defaults_applied[].value` | `json` | req | checked |  | The value applied |
| `defaults_applied[].reason` | `text` | req | checked |  | Why. Example: `no hardware stated` |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

Caveats about the request (vague, incomplete, contradictory) go in the Artifact's `issues`, not in the value ([Artifact](../schemas/artifact.md)).

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.research_brief_ids_resolve.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/research_brief.py:research_brief_ids_resolve` | muk | `requirement_id` values are unique across both requirement lists; `metric_id` values are unique; every `metrics[].requirement_id` names a requirement |
| `check.research_brief_defaults_disjoint.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/research_brief.py:research_brief_defaults_disjoint` | muk | no field is both in `defaults_applied` and quoted in `constraints.compute.quotes`, and every compute field present is in exactly one of them |

Checks that need the intake, such as whether each quote really appears in its source, belong to the producing capsule ([requirement capsule](../m1/requirement-capsule.md)).

## Example

For the prompt `Reduce the VRAM use of my model's attention by at least 30% without losing more than 1% accuracy. Don't retrain from scratch.`:

```json
{
  "objective": "Reduce attention-layer VRAM use while keeping accuracy close to the baseline.",
  "objective_evidence": "Reduce the VRAM use of my model's attention",
  "in_scope_items": [{"item": "the model's attention layers", "evidence": "my model's attention", "evidence_source_id": "prompt"}],
  "out_of_scope_items": [{"item": "retraining from scratch", "evidence": "Don't retrain from scratch", "evidence_source_id": "prompt"}],
  "constraints": {
    "compute": {"hardware": "single_gpu", "runtime_limit_s": 3600, "quotes": []},
    "frameworks": [], "other_limits": []
  },
  "mandatory_requirements": [
    {"requirement_id": "R1", "statement": "VRAM reduction of at least 30%", "evidence": "by at least 30%", "evidence_source_id": "prompt"},
    {"requirement_id": "R2", "statement": "accuracy loss of at most 1%", "evidence": "without losing more than 1% accuracy", "evidence_source_id": "prompt"}
  ],
  "optional_preferences": [],
  "metrics": [
    {"metric_id": "M1", "requirement_id": "R1", "name": "vram_reduction", "comparator": "gte", "target": 30, "unit": "percent", "evidence": "by at least 30%", "evidence_source_id": "prompt"},
    {"metric_id": "M2", "requirement_id": "R2", "name": "accuracy_loss", "comparator": "lte", "target": 1, "unit": "percent", "evidence": "without losing more than 1% accuracy", "evidence_source_id": "prompt"}
  ],
  "defaults_applied": [
    {"field": "constraints.compute.hardware", "value": "single_gpu", "reason": "no hardware stated"},
    {"field": "constraints.compute.runtime_limit_s", "value": 3600, "reason": "no runtime stated"}
  ]
}
```

## History

Moved here from the [requirement capsule](../m1/requirement-capsule.md) page, where it was drafted, so it has one definition. Changes when it moved, each from a CC rule or a recorded open item:

| Change | Why |
|---|---|
| `brief_version` removed | the Artifact's `type` and the pinned vocabulary already say the version (INV-5) |
| closed core with `ext` | requirement page Open 8: a field nobody declared must not be relied on (INV-14) |
| `evidence_source_id` on every quote | requirement page Open 7: a document's claim must not pass as the user's requirement |
| `constraints.compute.quotes` | requirement page Open 6: compute limits had no quotes, so nothing checked them |
| `id` renamed `requirement_id` and `metric_id` | INV-12: ids end `_id` |
| `framework`, `other` renamed `frameworks`, `other_limits`; compute quotes in `quotes` | INV-12: lists are plural. `in_scope` and `out_of_scope`, the PRD's names (3.2.2), become `in_scope_items` and `out_of_scope_items`: one naming rule for every field, no exception |
| comparator `>=`, `<=` renamed `gte`, `lte` | one name per operator across CC, as in the `predicate_op` registry; enum values are lowercase words (INV-13) |
