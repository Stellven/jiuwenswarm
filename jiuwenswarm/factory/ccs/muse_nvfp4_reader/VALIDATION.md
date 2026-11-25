# Validation and gate rules

The verifier half is `verify` (the converter diff) and `verify_pack` (the written pack). Each returns
`{"done": bool, "checks": [{name, status, stage, detail}], "stage_reached", "not_done_because"}`. `done` is false
whenever a check fails, when the required stage (`verify`: `require_stage`, default `runtime acceptance`;
`verify_pack`: `native CC execution`) was not reached, when a check that stage needs was `skipped`, and when an
`inconclusive` check was not settled by a passing runtime acceptance stage. `stage_reached` is the highest stage
with a pass where no check of it or a lower stage failed or was skipped. The factory host (`node_check.assess`)
then fails the output. A gate is a check that fails closed: when it fails the worker stops at that step.
`skipped`, `info` and `inconclusive` never stand in for a pass.

## Evidence stages (`node_check.STAGES`)

| Stage | Checks | Runs when |
| --- | --- | --- |
| `fixture` | `fixture_calibration` | Always. The bundled `good.diff` must pass, every planted fault must fail its named rule and every undecidable fault (`mapping-inconclusive.diff`) must not pass on this base; `inconclusive` when the fixtures do not apply (the base is not stock 9048bad8), so only runtime acceptance can carry the verdict. |
| `native CC execution` | static rules below | Always (stdlib + git). |
| `runtime acceptance` | tiny checkpoint conversion and comparison | With `python` (venv with torch, safetensors, numpy, transformers; default the controller interpreter if it has them) and `tiny_checkpoint` or `tiny_base`. Missing either: `tiny_conversion` fails when this stage is required, is `skipped` otherwise. |

The `ingest_nvfp4` contract requires stage `runtime acceptance` for `converter`: the tiny conversion round trip
is the bar for correctness, so the node closes only where the conversion venv and the tiny checkpoint exist
(the Spark). `verify_pack` checks are all `native CC execution` (the contract's stage for `nvfp4_pack`).

The rules judge only the change under review (`base`, default HEAD; `diff_path` or the working changes against
it). An earlier node's uncommitted change in the same checkout is carried with `carried_diff` (or committed
first); otherwise its paths fail `allowed_paths`.

## Converter gates (`verify`)

| Check | Fails when |
| --- | --- |
| `patch_input` | No change, unreadable diff, or a hunk does not apply to HEAD. |
| `fixture_calibration` | The static rules let a planted fault through, or fail `good.diff`, on this tree. |
| `allowed_paths` | Any path outside `conversion/*.py`. |
| `protected_paths` | Any edit under `gguf-py/`, `src/`, `ggml/`, `include/`, `common/`, `tools/` or to `convert_hf_to_gguf.py`. |
| `plain_text_edits` | Binary, mode, rename or delete. |
| `python_parses` | A touched file does not parse. |
| `stacked_reader` | No method in a `conversion/` class reads `gate_up` experts with `weight_scale` and repacks them. |
| `reuses_stock_pack` | The reader does not call the stock `_nvfp4_pack`. |
| `no_requantize` | The reader calls any `*quantize` function. |
| `lazy_repack` | `_nvfp4_pack` runs in the reader's own body (eager), `_repack_nvfp4` / `_flush_nvfp4_experts` is called for stacked experts, the body (outside deferred code) loads a packed weight or block scale (`to_eager(...)`, `.numpy()`, `np.asarray(...)`, or calling its `model_tensors` loader for anything but `.shape`/`.dtype`; the small `_weight_scale_2` / `_input_scale` vectors may be eager), no `LazyNumpyTensor`/`LazyTorchTensor` is built, or the deferred function is not handed to it. |
| `separate_gate_up_scales` | A scale is reduced (`sum`/`mean`/...) or no `[:, column]` selection exists. |
| `gate_up_mapping` | Recognized `(TYPE, row_start, row_end, column)` rows put gate off rows `[0, I)` or off scale column 0, or up off `[I, 2I)` / column 1. `inconclusive` when written another way: then `done` needs a passing runtime acceptance stage. |
| `scale_tensors_written`, `input_scale_written` | No `.scale` / `.input_scale` tensor name is written. |
| `stock_hook_chained` | `inconclusive` when the override does not call the stock hook (settled only by runtime acceptance). |
| `tiny_conversion` | The tree's `convert_hf_to_gguf.py` fails on the tiny NVFP4 checkpoint (capped, niced), or (when runtime acceptance is required) no conversion python or tiny checkpoint was given. |
| `expert_types` | A quantized layer's gate/up/down expert weight is not type 40 or has the wrong `[in, rows, E]` shape. |
| `blocks_bit_exact` | Any byte differs from the verifier's own repack of the source nibbles and E4M3 scales (gate = rows `[0, I)`); the detail says when a tensor holds the other half. |
| `expert_scales` | `.scale` missing, not `[E]`, or not exactly `weight_scale_2[:, 0]` (gate), `[:, 1]` (up), `[E]` (down). |
| `input_scales` | `.input_scale` missing or not equal to the source column. |
| `excluded_layers_kept` | An excluded layer's experts became NVFP4 or got a `.scale`. |
| `effective_weights` | `dequant(gguf) * .scale` differs from the checkpoint's own dequantization by more than 1e-6 relative. |

## Pack gates (`verify_pack`)

| Check | Fails when |
| --- | --- |
| `pack_readable` | A shard is missing, a header is unreadable or a tensor runs past its file. Nothing else is judged. |
| `layer_plan` | No or unreadable `source_index`; the index names no quantized layer (an all-BF16 pack is not an NVFP4 pack); a given `inventory` or `quantized_layers` disagrees with the index. The plan is never taken from an agent-written inventory. |
| `expert_layers_complete` | A layer lacks gate/up/down experts, or the pack's expert layers differ from the checkpoint's. |
| `expert_types` | A routed expert weight of a quantized layer is not nvfp4. |
| `expert_scales` | `.scale` missing, not F32 `[n_expert]` (= `expert_count`), or holds a non-positive or NaN value. |
| `input_scales` | The checkpoint has input scales for a layer but the pack does not (or wrong type/shape). |
| `scale_values` | A sampled layer's (`scale_sample_layers`, default all quantized) `.scale` / `.input_scale` differs from the checkpoint's `_weight_scale_2` / `_input_scale` column (gate 0, up 1, down the vector), read from the shard header plus a small range read; the detail says when gate and up hold each other's column. Fails when the shard data is not beside the index. |
| `excluded_layers_kept` | An excluded layer's experts are not at the checkpoint dtype read from the shard header (any float when the header is missing) or carry a `.scale`. |
| `nvfp4_only_on_experts` | NVFP4 anywhere but routed experts. |
| `tensor_types` | A type outside `allowed_types` (default f32, f16, bf16, nvfp4). |
| `total_bytes` | Outside `expect_bytes_range` when given (`info` otherwise). |

## Planted faults

`tests/fixtures/*.diff` are diffs against stock `conversion/muse_spark.py` (complete diffs are verifier fixtures,
never actor material). `good.diff` is the spike's converter change.

| Fixture | Static check that fails | Runtime checks that fail (with `python`) |
| --- | --- | --- |
| `gate-up-swapped.diff` | `gate_up_mapping` | `blocks_bit_exact` (holds the other half), `expert_scales`, `input_scales`, `effective_weights` |
| `scale2-columns-swapped.diff` | `gate_up_mapping` | `expert_scales` (holds the other column), `input_scales`, `effective_weights` |
| `input-scale-dropped.diff` | `input_scale_written` | `input_scales` |
| `eager-repack.diff` | `lazy_repack` | none: the tiny checkpoint cannot show the memory blow-up; the static rule is the gate |
| `eager-loader.diff` | `lazy_repack` (weights and block scales loaded with `to_eager` in the body, only the repack deferred) | none, as above |
| `mapping-inconclusive.diff` | none: `gate_up_mapping` is `inconclusive` (5-tuple parts, gate and up scale columns swapped), so `done` is false without runtime | `expert_scales` (holds the other column), `input_scales`, `effective_weights` |
| `touches-src.diff` | `allowed_paths`, `protected_paths` | not run (scope gate) |

`verify_pack` fixtures are built by `tests/muse_pack_fixture.py`: a 4-layer pack and the matching safetensors
checkpoint (`make_checkpoint`). Planted: dropped/zero/swapped (`swap_columns`) scales, wrong expert or excluded
types, an all-BF16 pack against an all-BF16 checkpoint (empty plan), an inventory that disagrees with the index.

```sh
python -m pytest jiuwenswarm/factory/ccs/muse_nvfp4_reader/tests -o addopts="" -q
MUSE_SPIKE_DIR=~/spike-muse-tiny MUSE_SPIKE_TREE=/tmp/wt-spike-llama python -m pytest .../tests -k runtime   # on the Spark
```

## What the checks do not establish

The static rules read the change; the runtime checks run it on a 4-layer, 16-expert checkpoint. Neither shows
the real conversion's peak memory, time or the full pack: those come from METHOD.md steps 5-6 (projection,
capped run, log) and `verify_pack`. `verify_pack` reads headers and the `[E]` scale vectors only; it does not
re-derive the 450 GB of blocks (the tiny runtime check is the bit-exactness evidence for the code that wrote them).
