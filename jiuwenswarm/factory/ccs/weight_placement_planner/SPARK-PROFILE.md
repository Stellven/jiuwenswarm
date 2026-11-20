# Spark activation profile

These settings are a source-derived Spark validation profile. Hold the stock, candidate gate-unset and candidate gate-enabled flags matched for each comparison, and retain the effective settings, logs, output parity and counters. Run under the approved capped wrapper. The strict stock reference keeps its documented four-slot configuration.

| Capsule | Matched stock control and candidate flags | Gate-on evidence |
| --- | --- | --- |
| Placement | Keep `-lm mmap` and all other strict-A settings. Replace `--cpu-moe` with an equivalent stock `-ot`. Stock and candidate gate unset take the full CPU expert override. Candidate gate on uses the precise complementary override and assigns the excluded expert tensor to CPU through a plan. | `LLAMA_PLACEMENT_PLAN=1` and `--placement-plan FILE`. Require one exact match, verify actual planned buffer against matched stock diagnostic readback, verify every CPU override still binds as expected, and retain stats and capped memory evidence. This is placement control activation and parity. Its expected effect is equivalent placement. |

Read the tensor inventory first and confirm that `blk.0.ffn_gate_exps.weight` exists. That tensor is created by the pinned DeepSeek41 loader for each applicable layer. The chosen target stays on CPU in all three arms. `--cpu-moe` injects the CPU regex `\.ffn_(up|down|gate|gate_up)_(ch|)exps`, and the loader uses `std::regex_search` on tensor names. Stock and candidate gate unset receive:

```bash
-ot '\.ffn_(up|down|gate|gate_up)_(ch|)exps=CPU'
```

Candidate gate on receives the complementary anchored expression:

```bash
-ot '^(?!blk\.0\.ffn_gate_exps\.weight$).*\.ffn_(up|down|gate|gate_up)_(ch|)exps=CPU'
```

The version 1 plan contains one anchored assignment:

```json
{"version": 1, "overrides": [{"pattern": "^blk\\.0\\.ffn_gate_exps\\.weight$", "buft": "CPU"}]}
```

Inspect the actual stock and candidate CUDA/CPU placement since the CPU selector can choose a more specific CPU buffer. Establish these matches against the inventory before launch. Avoid the full CPU override plus overlapping plan, which checks conflicts only after an attempted load and could retry. Use a small fixture for conflicting-rule tests. The planner's host device total and sum of host model buffers cannot establish 100 GiB cap compliance. Retain `bin/capped` evidence independently. A faster placement treatment would require changing actual buffers under a separate cap-reviewed stock placement comparison.
