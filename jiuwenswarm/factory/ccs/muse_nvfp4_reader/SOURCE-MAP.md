# llama.cpp source map (converter side)

Anchors checked with `git grep` in stock llama.cpp `9048bad8d6e3a0f9f1726e238e451181c7e02613`. Line numbers are
a guide only; find the names in the tree in front of you.

## Allowed paths

The change may edit **`conversion/*.py` only** (in practice `conversion/muse_spark.py`; `conversion/base.py`
if a shared hook truly needs a parameter). `verify` fails any other path.

## Edit

| Anchor | Why |
| --- | --- |
| `conversion/muse_spark.py` `class MuseSparkModel(TextModel)` (`:39`) | Home of the override. `model_arch = MUSE_SPARK`. |
| `conversion/muse_spark.py` `modify_tensors` (`:82`), `gate_up_proj` split (`:105`-`:111`) | The BF16 path: gate is `[:, :n_ff, :]`, up `[:, n_ff:, :]`, names from `format_tensor_name(FFN_GATE_EXP / FFN_UP_EXP / FFN_DOWN_EXP, bid)`. Your NVFP4 path must produce the same names and order. Excluded (BF16) layers keep using this path. |

## Read (reuse, do not change)

| Anchor | What it gives you |
| --- | --- |
| `conversion/base.py` `_generate_nvfp4_tensors` (`:1345`) | Stock NVFP4 reader: matches `*.weight` + `*.weight_scale` (per-expert names `experts.N.{gate,up,down}_proj`), skips FP8, eagerly loads each pair, collects per-expert scale_2 as `float(scale2.sum())` (wrong for a `[2]` gate/up pair), flushes per layer. Called once from the NVFP4 detection block (`:1521`-`:1544`) **before** the normal tensor pass; whatever it pops from `self.model_tensors` is never seen by `modify_tensors`. |
| `conversion/base.py` `_nvfp4_pack` (`:1310`, staticmethod) | The bit move from ModelOpt (nibble pairs + E4M3 per 16) to `block_nvfp4` (4 UE4M3 scale bytes + 32 code bytes per 64 values). Input: one expert's `[rows, in/2]` U8 and `[rows, in/16]` F8 tensors. Returns `(raw [rows, in/64*36] uint8, logical shape)`. |
| `conversion/base.py` `_repack_nvfp4` (`:1334`) | Single dense tensor: map name, pack, `add_tensor(raw_dtype=NVFP4)`, `_tag_prec_a4`, per-tensor `.scale` / `.input_scale`. Eager; fine for one dense tensor, not for stacked experts. |
| `conversion/base.py` `_flush_nvfp4_experts` (`:1426`) | Stacks per-expert raws with `np.stack` (eager) and writes `[E]` `.scale` / `.input_scale` through `_write_scales_tensor`. |
| `conversion/base.py` `_write_scales_tensor` (`:341`) | Writes an `[E]` F32 vector **unless every value is ~1.0** (then nothing is written). |
| `conversion/base.py` `_tag_prec_a4` (`:939`) | Marks W4A16 tensors; call it like the stock path does. |
| `conversion/base.py` `_mxfp4_expert_tensor` (`:1267`) | The pattern to copy: one stacked expert tensor as `gguf.LazyNumpyTensor(meta=..., args=(loaders,), func=load)`; loaders go through `args`, the load function runs at write time. |
| `conversion/base.py` `class LazyTorchTensor` (`:3350`), `LazyTorchTensor.to_eager` | `self.model_tensors[name]` is a callable returning a lazy tensor; `fn().shape` reads only metadata; `to_eager(fn())` reads the bytes. |
| `gguf-py/gguf/lazy.py` `class LazyNumpyTensor` (`:206`), `meta_with_dtype_and_shape` (`:212`) | Meta tensor for the writer's size planning. |
| `gguf-py/gguf/constants.py` `NVFP4 = 40` (`:7151`), block `(64, 4 + 32)` (`:7395`) | Type id and block size (36 bytes per 64 values). |
| `gguf-py/gguf/quants.py` `dequantize` (`:69`) | Used by the verifier to dequantize your blocks; handy for your own checks too. |
| `convert_hf_to_gguf.py` `--outtype` (`:60`), `--use-temp-file` (`:73`), `--split-max-size` (`:93`), `--dry-run` (`:97`), local gguf-py import (`:14`) | Output type of the BF16 modules (`bf16`), shard size (`50G`), dry run to list tensors. |

## Protected (never edit in this node)

`gguf-py/` (writer, constants, quants), `src/` (the loader and graph: `src/llama-model.cpp:1897`-`:1963` already
create `ffn_*_exps.scale` / `.input_scale` as `TENSOR_NOT_REQUIRED`; the Muse graph is wired by
`weights.build_expert_scale_wiring`), `ggml/`, `include/`, `common/`, `tools/`, `convert_hf_to_gguf.py`.
