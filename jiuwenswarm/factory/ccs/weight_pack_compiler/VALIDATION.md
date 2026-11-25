# Validation and gate rules

The verifier half of the capsule is `verify_recipe` and `verify_pack`. Each returns
`{"done": bool, "checks": [{name, status, stage, detail}]}` with stage `native CC execution`. `done` is false
whenever any check fails; the factory host (`node_check.assess`) then fails the output. The gate rules below are
those failing checks: when one fails, the worker halts at that step and reports it. A skipped or info check
never stands in for a pass.

## Recipe gates (`verify_recipe`; halt before converting)

| Check | Halts when |
| --- | --- |
| `target_given` | No `target` input (required; a call without it is refused as `verification_input`). |
| `recipe_format` | Not `factory.pack-recipe/1`, or `source`, `target`, `tensors`, `argv` or `estimate` is missing. |
| `target_matches` | The recipe's target differs from the requested `target`. |
| `source_digests` | A source file has no sha256 (a header digest is not enough to name the source pack). |
| `source_matches_recipe` | The source headers (`pack_manifest`, required) differ from the recipe in tensor names, types, shapes or file sizes. |
| `expert_targets` | A routed expert weight does not target the requested type, is already that type in the source headers (pinning experts to their source type is not a requantization), or none was found. |
| `non_expert_kept` | Any other tensor's target differs from its type in the source headers (not the recipe's claim). |
| `gb10_kernel_types` | A converted type is outside the admitted GB10 list: q2_k q3_k q4_k q5_k q6_k q8_0 q4_0 q4_1 q5_0 q5_1 iq2_xxs iq2_xs iq2_s iq3_xxs iq3_s iq4_xs iq4_nl mxfp4 nvfp4 f16 bf16 f32 (all have stock CUDA kernels at 9048bad8). |
| `block_divisibility` | A converted tensor's `ne[0]` is not a multiple of the target block (stock would silently fall back). |
| `argv_parses` | Stock would print usage: unknown flag, flag after a positional, malformed `--tensor-type`, bad ftype, `--include-weights` with `--exclude-weights`. |
| `allow_requantize` | `--allow-requantize` is absent. |
| `argv_scope` | The full-run argv carries `--prune-layers`, `--dry-run`, `--pure` or `--leave-output-tensor`. |
| `argv_realizes_targets` | Replaying the argv through the verifier's own model of stock type selection (`helpers/stock_quantize.py`) gives any tensor a type other than its recipe target, or leaves a quantizable tensor unpinned. |
| `argv_input_is_source`, `argv_output_not_source` | The argv reads another pack or would overwrite a source file. |
| `imatrix_named` | Target below 3.5 bpw and no imatrix with sha256 in the recipe, or `--imatrix` names a different file. |
| `estimate_consistent` | The recipe's data bytes differ from the recomputation from ggml block sizes, or its header allowance is implausible. |
| `disk_grant` | The temporary peak exceeds the grant, or is below the output size. Skipped when no grant is given. |

## Pack gates (`verify_pack`; the output fails, nothing is published)

| Check | Halts when |
| --- | --- |
| `pack_readable` | A shard is missing, a header is unreadable or truncated, a type id is unknown, or a tensor runs past its file. Fails closed: nothing else is judged. |
| `source_readable`, `target_given` | `source_pack` or `target` missing or unreadable (both required). |
| `target_matches` | With a recipe: its target differs from the requested `target`. |
| `expert_types` | A routed expert weight is not the target type, or still has its source type (for example left NVFP4). |
| `non_expert_types` | A non-expert tensor differs from its type in the source pack headers (never from the recipe). Fails closed without `source_pack` and `target`. |
| `tensor_set` | A tensor was dropped, added or reshaped against the source headers. |
| `scale_tensors_present` | An `ffn_*_exps.scale` / `.input_scale` tensor of the source is absent. Fails closed without `source_pack`. |
| `scale_tensors_identical` | Its bytes or type differ from the source. |
| `source_is_recipe_source` | `source_pack` is not the pack the recipe was planned from. |
| `total_bytes` | Total size is outside `expect_bytes_range` (required; contract: 250-320 GB). Fails without the range. |
| `recipe_size` | Total size is off the recipe estimate by more than the header allowance. |
| `shard_layout` | With `--keep-split` the shard count differs from the source. |
| `imatrix_recorded` | The recipe names an imatrix but the output lacks `quantize.imatrix.file` with that name (the tool writes it when it used the file). |

## Planted faults (capsule tests)

`tests/test_wpc_capabilities.py` builds tiny GGUF v3 packs and plants one fault per case. Recipe: missing
`--allow-requantize`, an expert retargeted, an attention tensor retargeted, a dropped pin, no imatrix, no
sha256, an unknown flag, `--prune-layers` in the full run, a forged byte estimate, a type without a GB10 kernel,
a disk grant overrun, a different source pack, a recipe target other than the requested one, experts pinned
to their source type, a recipe lying about `output.weight`'s source type. Pack: attention requantized, a dropped
`.scale`, changed `.scale` bytes, an expert left NVFP4, experts left at the source type with target = source,
`output.weight` requantized under a recipe that claims it, a missing shard, a truncated header, size outside the
range, no imatrix record, no reference, no target or range. Each fault must fail its named check and the clean case must pass.

```sh
python -m pytest jiuwenswarm/factory/ccs/weight_pack_compiler/tests -o addopts="" -q
python -m pytest tests/factory/test_weight_pack_compiler_cc.py -o addopts="" -q --noconftest
```

## What the checks do not establish

The verifiers read headers and the small scale tensors. They do not establish that the Q2_K blocks encode the
NVFP4 weights well, that the pack loads, or that it is coherent: those come from the probe, the stock tool's
log (no `falling back to` line) and the coherence smoke in METHOD.md step 7.
