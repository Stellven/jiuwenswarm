# Spark matched activation profiles

Profile revision 1.1.3. These source-derived acceptance probes await runtime validation. Use one process under `bin/capped`, a unique output directory for each run, the pinned model, the same fixed requests, and the same hardware state within each pair. Append the effective slots, threads, context, batch, ubatch, checkpoints, load mode, buffers, and native-cache state from startup logs to each profile receipt. Leave all unrelated capsule and `LLAMA_ARG_*` environment overrides unset. Use `-lv 4` in each acceptance arm for INFO markers. Keep that instrumentation decision visible when choosing timed-trial options. Use greedy token and output byte parity, plus explicit runtime engagement checks, before timing.

Strict A uses `-lm mmap --cpu-moe` and stock defaults, except loopback service host and port. Keep the original strict A as a reference. Do not trace a speed difference to a component when the stock control uses different scheduling, cache policy, or placement. A+ uses an independent native-cache policy. For each profile below run stock, candidate gate unset, then candidate gate enabled. Keep stock and candidate binaries and model SHA identities in the ledger. Log cold starts separately and discard the first request for warm profiling.

| Capsule | Stock flags and matching candidate controls | Gate-on acceptance evidence |
| --- | --- | --- |
| Recorder | Strict A for all three. Assign a fresh absent JSONL pathname for the enabled arm, and shut down normally. | `LLAMA_EVENT_REC=/absolute/path/events.jsonl`. One active and one stats marker, exact unique (microbatch, layer) coverage against an independent dispatch manifest, `expected=written`, `lost=0`, phase coverage, route and bytes validity. Compare overhead between same binary gate unset and gate set. Activation at open alone is insufficient. |
| Cache | Strict A for all three, with native MoE cache disabled. A separate A+ triplet exercises the documented bypass. | `LLAMA_EXPERT_CACHE=1 LLAMA_EXPERT_CACHE_MIB=64`. Confirm effective mmap and CUDA selected-copy traffic, one active line and one stats line, positive leases, reuses and `bytes_copied_saved`, and peak within the admitted budget. Saved upload bytes are a counter, not total memory traffic or elapsed-time evidence. |
| Predictor | Strict A fallback. For active probe use A with `-np 1 -c 4096` in all three arms, native MoE cache disabled. Admission requires causal text prefill and actual mapped expert selected-copy callbacks. | `LLAMA_EXPERT_PREDICT=1`. One active and one stats marker, forecast activity, hits and misses, waste, lead samples and lead time with greedy parity. Test 2048 tokens first. The literal `bytes_useful_at_consumption=0` does not establish avoided physical I/O. Run separate inactive tests for default slots and native cache. |
| Mapper | Strict A fallback. For active probe use A with `-np 1 -c 4096 --ctx-checkpoints 0 -b 2047 -ub 512` in all three arms. Use the exact uncached 2048-token prompt to cross the logical cut. Confirm effective widths and retained emission under this profile. | `LLAMA_BATCH_LAYOUT=1`. Require `active n_batch=2047 n_ubatch=512 limit=1536`, contiguous planned spans, a changed cut and positive decisions/rows. For the ordinary splitter, stock spans of 2047/1 predict five physical microbatches and aligned spans of 1536/512 predict four. Check actual spans before attributing an effect. Confirm no rolling checkpoint path is exercised in the active probe. Run the capsule's small boundary sweep separately. |
| Placement | Keep `-lm mmap` and all other strict-A settings. Replace `--cpu-moe` with an equivalent stock `-ot`. Stock and candidate gate unset take the full CPU expert override. Candidate gate on uses the precise complementary override and assigns the excluded expert tensor to CPU through a plan. | `LLAMA_PLACEMENT_PLAN=1` and `--placement-plan FILE`. Require one exact match, verify actual planned buffer against matched stock diagnostic readback, verify every CPU override still binds as expected, and retain stats and capped memory evidence. This is placement control activation and parity. Its expected effect is equivalent placement. |

## Placement plan and paired stock control

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

## Combined D

Compose the verified candidate changes against the same stock base through the five capsule methods. Record the selected capsule versions, input commit/diff IDs and explicit overlap resolutions as factory evidence. First preserve the stock call path when every gate is unset. Compose recorder/predictor eval ask/read requests as a union, forwarding each caller's stop semantics only for requested reads, chaining the original callback once, and restoring it once. Observe original expert IDs before native cache remapping. Compose cache leases and copies once per dispatch lifetime, account for host submissions separately from device fills and hits, and restore the stock copy callback on all exits. Keep mapper dispatch boundaries and placement admission owned by their respective methods. Inspect overlapping CMake, context and server scopes through each capsule verifier. Save all checks and accepted static scopes before compiling, then collect runtime gate-unset parity and per-component counters on the same combined binary.

For an all-gates-on probe, use the mapper's single-slot checkpoint-free profile with the compatible equivalent placement pair, native MoE cache disabled, and each enabled gate's counters. Test one gate on at a time on the combined binary before enabling all five. Record both combined and single-gate effective settings. Strict A disables predictor/mapper; A+ also bypasses predictor/cache. An all-gates-run can only support a timing claim against matched stock for its own profile.
