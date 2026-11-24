# Validation and gate rules

The verifier half is `verify`. It returns `{"done": bool, "checks": [{name, status, stage, detail}]}`; `done` is
false whenever a check fails and the factory host (`node_check.assess`) then fails the output. A gate is a check
that fails closed. `skipped`, `info` and `inconclusive` never stand in for a pass and never count toward the
stage reached. The verifier never writes inside the checkout: it reads HEAD with git, exports trees with
`git archive` into `work_dir` and builds there.

## Evidence stages (`node_check.STAGES`)

| Stage | Checks | Runs when |
| --- | --- | --- |
| `fixture` | `fixture_calibration` | Always: `good.diff` passes and each planted fault fails its rule on this HEAD (`skipped` when the fixtures do not apply, i.e. HEAD is not stock 9048bad8 here). |
| `native CC execution` | static rules; tiny-pack preconditions | Always (stdlib + git). |
| `compile` | `compile` (candidate), `stock_build` (info) | Unless a static gate failed or `build: false`. Needs cmake and a C++ toolchain. |
| `runtime acceptance` | `scale_free_parity`, `nvfp4_kld`, `no_nan`, `expert_slice` | With `tiny_dir`. Reached **only when all four ran and passed**; if any could not run, the others are demoted to `info`. |

The `wire_expert_scales` contract requires `runtime acceptance`: on the factory host without `tiny_dir` (or
without a build toolchain) the node cannot pass. With a stock build cached in `work_dir`, a full verify took
75 s on the Spark (CPU, `-j 8`); with both builds cold, 2 min. `FACTORY_VERIFY_TIMEOUT` defaults to 900 s.

## Gates

| Check | Fails when |
| --- | --- |
| `patch_input` | No change, unreadable diff, or a hunk does not apply to HEAD. |
| `fixture_calibration` | The static rules let a planted fault through, or fail `good.diff`, on this tree. |
| `allowed_paths` | Any path other than `src/models/muse-spark.cpp`. |
| `protected_paths` | Any edit under `ggml/`, `gguf-py/`, `include/`, `conversion/`, `common/`, `tools/`. |
| `plain_text_edits` | Binary, mode, rename or delete. |
| `moe_call` | Not exactly one `build_moe_ffn` call before and after, or the call matches no declaration in `src/llama-graph.h`. |
| `scale_args` | `up_exps_s`, `gate_exps_s`, `down_exps_s` (bound by parameter name) are not exactly `model.layers[il].ffn_{up,gate,down}_exps_s`; the detail names a scale used twice or left null. |
| `call_otherwise_unchanged` | Any other argument of the call differs from HEAD, or the argument count changed. |
| `edits_confined_to_call` | Code outside the call changed (comments and whitespace ignored). |
| `bf16_pack_present` etc., `parity_pack_scale_free`, `numerics_pack_scaled` | The tiny packs are missing, the parity pack carries `.scale` tensors, or the NVFP4 pack has no NVFP4 experts or scales (bad inputs fail closed). |
| `compile` | The CPU build of `llama-simple`, `llama-perplexity`, `llama-eval-callback` fails. |
| `scale_free_parity` | Greedy `llama-simple -n 32` stdout on the scale-free pack differs from stock's (or either run fails). |
| `nvfp4_kld` | Mean KLD of the NVFP4 pack vs the dequantized reference above `kld_max` (default 0.005), or the run fails. |
| `no_nan` | KLD or PPL(Q) not finite. |
| `expert_slice` | For the first quantized layer, any of `ffn_moe_gate`, `ffn_moe_up`, `ffn_moe_down`, `ffn_moe_out` differs from the reference by more than `slice_tol` (default 0.05) in max abs diff / max abs reference over the printed values. |
| `stock_control` | `info` only: the stock graph on the same NVFP4 pack (NaN at 9048bad8). |

Why `expert_slice`: Muse RMS-normalizes each expert's output (`ffn_post_exp_norm`) before weighting, so a per-expert
factor on up or down nearly cancels before the logits. On the Spark the planted faults below kept KLD at
0.0013 (same as the good change); only the matmul-level slice and the static `scale_args` rule see them.

## Planted faults

`tests/fixtures/*.diff` are diffs against stock `src/models/muse-spark.cpp` (verifier fixtures, never actor
material). `good.diff` is the spike's graph change.

| Fixture | Static | Runtime (with `runtime_even_if_static_fails`) |
| --- | --- | --- |
| `up-gets-gate-scale.diff` | `scale_args` | `expert_slice` (`ffn_moe_up-1`); KLD unchanged |
| `down-scale-missing.diff` | `scale_args` | `expert_slice` (`ffn_moe_down-1`); KLD unchanged |
| `touches-ggml.diff` | `allowed_paths`, `protected_paths` | passes (the added header is unused): scope is the gate |

```sh
python -m pytest jiuwenswarm/factory/ccs/expert_scale_wiring/tests -o addopts="" -q
```

## What the checks do not establish

The runtime checks run a 4-layer, 16-expert random model on CPU. They do not establish CUDA numerics on GB10
(MMQ activation path), the real pack's coherence, or speed; those are the base-engine smoke and later nodes.
