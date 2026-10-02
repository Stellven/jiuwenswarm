---
type: payload-type
id: cc.type.hypothesis_blueprint
version: 2
status: blackbox
tags: [types, m1]
---

# `hypothesis_blueprint`: the frozen experiment contract · version 2

The pre-registered claim, methods, resources and thresholds for PRD 3.5. Produced by [Hypothesis](../m1/hypothesis.md), read by POC, Benchmark, Evaluation and Report. This technical contract keeps readings 41 and 44 explicit; their product classification policy remains blocked. Repository input is supplied by intake version 2, not a reference document. Measurement methods must already exist in the trusted registry before POC generation; issue 58 owns missing methods.

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `claim` | `text` | req | checked |  | One testable technical claim |
| `independent_variable` | `text` | req | checked |  | The intervention |
| `metrics` | `list<object>` | req | checked |  | At least one. Unique metric IDs; all mandatory Brief metrics preserved |
| `metrics[].metric_id` | `id` | req | checked |  | Stable experiment metric ID |
| `metrics[].brief_metric_id` | `id?` | req | checked |  | Brief metric being preserved, or null for a separately registered metric |
| `metrics[].name` | `string` | req | checked |  | Human-readable metric label |
| `metrics[].role` | `enum(goal, guard)` | req | checked |  | Goal or non-degradation constraint; never inferred downstream |
| `metrics[].raw_unit` | `string` | req | checked |  | Unit of each arm's measured value, such as GB or fraction |
| `metrics[].unit` | `string` | req | checked |  | Unit of the threshold comparison, such as percent or GB |
| `metrics[].basis` | `enum(absolute, delta, relative_percent, percentage_points)` | req | checked |  | Transformation defined by the measurement protocol |
| `metrics[].better` | `enum(higher, lower)` | req | checked |  | Direction of improvement in the raw measured quantity |
| `metrics[].expected` | `number` | req | checked |  | Expected claim effect, distinct from the acceptance target |
| `metrics[].expected_comparator` | `enum(lt, lte, gt, gte, eq)` | req | checked |  | Predicate for meeting the claim |
| `metrics[].falsified_at` | `number` | req | checked |  | Pre-registered falsification boundary |
| `metrics[].falsification_comparator` | `enum(lt, lte, gt, gte, eq)` | req | checked |  | Predicate that falsifies this metric's claim |
| `metrics[].acceptance_target` | `number?` | req | checked |  | Brief target translated to this basis without weakening; null only when the Brief has none |
| `metrics[].acceptance_comparator` | `enum(lt, lte, gt, gte, eq)?` | req | checked |  | Null exactly when acceptance_target is null |
| `metrics[].method_id` | `id` | req | checked |  | Trusted registered measurement method |
| `metrics[].method_sha256` | `sha256` | req | checked |  | Immutable method implementation and configuration-schema hash |
| `metrics[].statistic` | `enum(mean, median, minimum, maximum)` | req | checked |  | Declared aggregation across repeats |
| `baseline_resource_id` | `id` | req | checked |  | A project_asset in intake |
| `dataset_resource_id` | `id` | req | checked |  | A validation_data resource in intake |
| `resource_snapshot_sha256` | `sha256` | req | checked |  | Committed read-only baseline/dataset snapshot manifest |
| `benchmark_config_sha256` | `sha256` | req | checked |  | Frozen method-validated benchmark settings; includes declared hardware |
| `repeats` | `integer` | req | checked |  | Positive repeat count fixed before code generation |
| `seed` | `integer` | req | checked |  | Same seed policy for baseline and treatment; protocol owns expansion |
| `mechanism` | `object` | req | checked |  | Proposed intervention |
| `mechanism.description` | `text` | req | checked |  | Description of the intervention |
| `mechanism.file` | `string` | req | checked |  | Snapshot-relative Python file identified by CodeSearch |
| `mechanism.line` | `integer` | req | checked |  | Positive line in that snapshot |
| `verification_plan` | `list<text>` | req | checked |  | At least one. Ordered protocol steps |
| `ext` | `map<string, json>` | opt | checked |  | Producer extensions; consumers ignore |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | Generated schema matches |
| `blueprint_contract` | deterministic | `outputs` | `both` | `cc/checks/registry/research.py:blueprint_contract` | muk | Unique metrics; positive repeats and line; paired nulls; method/config and snapshot exist; mandatory Brief targets translated without weakening; threshold predicates and basis approved before generation |

Cross-input checks resolve the intake and Brief from the owning Observation; the payload carries no run or step ID. The frozen Artifact is the authority. Method/dataset/threshold changes require a new run. [Measurement protocol](../m1/measurement-protocol.md) defines all arithmetic. A claimed expected effect is never silently replaced by the Brief target.

## Example

```json
{
  "claim": "Tiled attention reduces peak VRAM by 40%.",
  "independent_variable": "attention kernel",
  "metrics": [
    {
      "metric_id": "M1",
      "brief_metric_id": "M1",
      "name": "peak_vram",
      "role": "goal",
      "raw_unit": "GB",
      "unit": "percent",
      "basis": "relative_percent",
      "better": "lower",
      "expected": 40,
      "expected_comparator": "gte",
      "falsified_at": 10,
      "falsification_comparator": "lt",
      "acceptance_target": 30,
      "acceptance_comparator": "gte",
      "method_id": "peak_vram",
      "method_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "statistic": "mean"
    }
  ],
  "baseline_resource_id": "project-1",
  "dataset_resource_id": "validation-1",
  "resource_snapshot_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "benchmark_config_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
  "repeats": 1,
  "seed": 1234,
  "mechanism": {
    "description": "Replace the attention forward pass with a tiled kernel.",
    "file": "model.py",
    "line": 45
  },
  "verification_plan": [
    "Run baseline then treatment with identical data and seed",
    "Capture peak VRAM and compare frozen predicates"
  ]
}
```
