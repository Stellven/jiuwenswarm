# Validation and gate rules

The verifier half is `verify`. It returns `{"done": bool, "checks": [{name, status, stage, detail}],
"stage_reached", "not_done_because"}`; `done` is false whenever a check fails, when `require_stage` (default
`runtime acceptance`) was not reached, when a check that stage needs was `skipped` (compile, runtime), and when an
`inconclusive` check (an uncalibrated `fixture_calibration`) was not settled by a passing runtime acceptance stage.
The factory host (`node_check.assess`) then fails the output. A gate is a check that fails closed. `skipped`,
`info` and `inconclusive` never stand in for a pass. The verifier never writes inside the checkout: it reads the
base (default HEAD) with git, exports trees with `git archive` into `work_dir` and builds there.

## Evidence stages (`node_check.STAGES`)

| Stage | Checks | Runs when |
| --- | --- | --- |
| `fixture` | `fixture_calibration` | Always: `good.diff` passes and each planted fault fails its rule on this base (`inconclusive` when the fixtures do not apply, i.e. the base is not stock 9048bad8: then only runtime acceptance carries the verdict). |
| `native CC execution` | static rules; tiny-pack preconditions | Always (stdlib + git); the tiny packs are judged before any build. |
| `compile` | `compile` (candidate), `stock_build` (info) | Unless a static gate failed, the tiny packs are unusable or `build: false`. Needs cmake and a C++ toolchain (missing: `compile` fails when compile or runtime is required). |
| `runtime acceptance` | `scale_free_parity`, `nvfp4_kld`, `no_nan`, `expert_slice` | With `tiny_dir` (missing: `runtime_acceptance` fails when required). Reached **only when all four ran and passed**; if any could not run, the others are demoted to `info`. |

Only the change under review is judged. If the checkout also holds the reader node's uncommitted converter change
(`conversion/*.py`), carry it: commit it first (`base` HEAD), pass `diff_path` with only the graph change, or pass
the reader's patch as `carried_diff`; otherwise `allowed_paths` fails.

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
| `scale_args` | `up_exps_s`, `gate_exps_s`, `down_exps_s` (bound by parameter name) are not the member expressions `model.layers[il].ffn_{up,gate,down}_exps_s` (whitespace aside; no alias, see GUIDE.md); the detail names a scale used twice or left null. |
| `call_otherwise_unchanged` | Any other argument of the call differs from HEAD, or the argument count changed. |
| `edits_confined_to_call` | Code outside the call changed (comments and whitespace ignored). |
| `bf16_pack_present` etc., `tiny_packs_distinct`, `tiny_packs_pinned`, `parity_pack_scale_free`, `numerics_pack_scaled`, `reference_pack_dequantized` | The tiny packs are missing; two of them are the same path or the same bytes (the reference must not be the NVFP4 pack); a pack differs from its sha256 in `tiny_packs_manifest` (when given); the parity pack carries `.scale` tensors; the NVFP4 pack has no NVFP4 experts or scales; the reference holds NVFP4 or `.scale` tensors. Bad inputs fail closed, before the build. |
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
