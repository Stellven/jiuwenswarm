---
type: payload-type
id: cc.type.benchmark_payload
version: 2
status: draft
tags: [types, m1]
prd: [3.7.3, 3.7.4]
level: detail
---

# `benchmark_payload`: empirical measurements · version 2

PRD: 3.7.3, 3.7.4

Baseline/treatment samples and their raw evidence, collected under PRD 3.7 without scientific grading. [Benchmark](../capabilities/benchmark.md) produces this; Evaluation and Report read it. Execution remains blocked until the platform boundary passes its [checks](../capsule/fields.md#term-check).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-benchmark-payload"></a>**benchmark_payload** (also: benchmark payload) | The baseline and treatment samples with their raw evidence, collected by Benchmark without any scientific grading. Evaluation and Report read it. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `seed` | `integer` | req | checked |  | Frozen blueprint seed |
| `runs` | `list<object>` | req | checked |  | At least one. Baseline then treatment for every declared repeat, in protocol order |
| `runs[].arm` | `enum(baseline, treatment)` | req | checked |  | Experimental arm |
| `runs[].repeat_index` | `integer` | req | checked |  | Zero-based repeat index |
| `runs[].seed` | `integer` | req | checked |  | Per-repeat seed; same for paired arms |
| `runs[].exit_status` | `integer` | req | checked |  | Containing harness process exit code, not a fabricated per-arm process code |
| `runs[].stdout_sha256` | `sha256` | req | checked |  | Raw capture of the containing harness; paired samples may share this hash |
| `runs[].stderr_sha256` | `sha256` | req | checked |  | Raw stderr capture |
| `runs[].measurement_ref` | `Ref(artifact)` | req | checked |  | Trusted measurement evidence tied to the [frozen](../system/lifecycle.md#term-freeze) method, arm, repeat, seed and actual workload |
| `runs[].values` | `map<string, number>` | req | checked |  | Finite raw values keyed by blueprint metric ID |
| `deltas` | `map<string, number>` | req | checked |  | Aggregated treatment minus baseline in raw units; never a percent or verdict |
| `unmeasured` | `list<id>` | req | checked |  | Every declared metric lacking a complete pair; may be empty |
| `ext` | `map<string, json>` | opt | checked |  | Producer extensions; consumers ignore |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | Generated schema matches |
| `benchmark_contract` | deterministic | `outputs` | `both` | `cc/checks/registry/research.py:benchmark_contract` | cc-team | Raw capture parses to these samples, arm/repeat/seed coverage matches blueprint, IDs and finite values match registered methods, arithmetic deltas recompute, frozen inputs and boundary evidence exist |

The [measurement protocol](../capabilities/measurement-protocol.md) defines missing samples and aggregation. A nonzero process exit, timeout or malformed required stream [halts](../system/lifecycle.md#term-halt) the stage; it cannot masquerade as a completed benchmark. All blueprint metrics are mandatory in M1; unmeasured is empty on a [released](../system/lifecycle.md#term-release) result. Partial samples and missing metrics are retained as failed [Observation](../schemas/observation.md#term-observation) evidence and never aggregated into a successful result.

## Example

```json
{
  "seed": 1234,
  "runs": [
    {
      "arm": "baseline",
      "repeat_index": 0,
      "seed": 1234,
      "exit_status": 0,
      "stdout_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "stderr_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "values": {
        "M1": 10
      },
      "measurement_ref": {
        "id": "measurement-0",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
      }
    },
    {
      "arm": "treatment",
      "repeat_index": 0,
      "seed": 1234,
      "exit_status": 0,
      "stdout_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "stderr_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "values": {
        "M1": 6.5
      },
      "measurement_ref": {
        "id": "measurement-1",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
      }
    }
  ],
  "deltas": {
    "M1": -3.5
  },
  "unmeasured": []
}
```
