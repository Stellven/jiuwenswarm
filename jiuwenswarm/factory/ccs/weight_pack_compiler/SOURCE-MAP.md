# llama.cpp source map

Anchors checked with grep in the pinned stock source at `9048bad8d6e3a0f9f1726e238e451181c7e02613`
(`D:/AI4Research/Inference Engines/llama.cpp`). Line numbers are those of that pin. The pack compiler edits no
engine file: it runs the stock `llama-quantize` binary, so every row is Read.

## The tool: `tools/quantize/quantize.cpp`

| Anchor | What it fixes for the recipe |
| --- | --- |
| `:34` `static const std::vector<quant_option> QUANT_OPTIONS` | File-type positional names (`Q2_K`, `Q2_K_S`, `Q3_K_M`, `Q4_K_M`, `IQ2_XXS`, ...). `Q3_K`, `Q4_K`, `Q5_K` are aliases of the `_M` mixes. |
| `:122` `static void usage(` | Full flag list: `--allow-requantize --leave-output-tensor --pure --imatrix --include-weights --exclude-weights --output-tensor-type --token-embedding-type --tensor-type --tensor-type-file --prune-layers --keep-split --override-kv --dry-run --max-buffer-size`, then `input [output] type [nthreads]`. |
| `:305` `static ggml_type parse_ggml_type(` | Type names are ggml type names, case-insensitive (`q2_K`, `nvfp4`, `bf16`, ...). |
| `:317` `static bool parse_tensor_type(` | `--tensor-type NAME=TYPE`: splits at the first `=`, **lower-cases NAME**, keeps it as a pattern string. |
| `:410`-`:485` flag loop | Flags must come before the positionals; an unknown `--flag` prints usage and exits. `--include-weights` / `--exclude-weights` select which tensors **use the imatrix**, not which are quantized, and cannot be combined. |
| `:439` `--prune-layers` | Comma list of layers to drop; used only for the timing probe. |
| `:447` `--dry-run` | Prints per-tensor target types and the final size without writing. |
| `:449` `--allow-requantize` | Sets `params.allow_requantize`; needed to convert an NVFP4 source. |
| `:471` `--keep-split` | Output keeps the input sharding. |
| `:564`-`:600` positionals | `input ftype` writes `ggml-model-<FTYPE>` next to the input; `input output ftype` uses `output`; with `--keep-split` a trailing `.gguf` is removed from `output` and it becomes the shard prefix. |

## The library: `src/llama-quant.cpp`

| Anchor | What it fixes |
| --- | --- |
| `:211` `tensor_type_patterns.emplace_back(std::regex(p->pattern), p->type)` | Each `--tensor-type` NAME is compiled as a std::regex (ECMAScript). |
| `:302` `static bool tensor_allows_quantization(` | Only 2D+ tensors whose name ends in `weight`, not `_norm.weight`, not `ffn_gate_inp.weight` (and some arch lists) are ever converted. 1D `.scale` / `.input_scale` tensors are copied. |
| `:459` `static ggml_type tensor_type_fallback(` | When `ne[0]` is not whole blocks: Q2_K/Q3_K/Q2_0/TQ* -> Q4_0; IQ1-IQ3/IQ4_XS -> IQ4_NL; Q4_K -> Q5_0; Q5_K -> Q5_1; Q6_K -> Q8_0; then F16 if still not divisible. |
| `:560` `if (arch == LLM_ARCH_MUSE_SPARK &&` | Muse mixture bumps latent and attention-gate tensors to Q8_0. A pinned tensor skips the mixture, so the recipe pins every non-expert tensor. |
| `:794` `static ggml_type llama_tensor_get_type(` | Order: not quantizable -> keep; `--token-embedding-type`; `--output-tensor-type`; then the first `--tensor-type` pattern with `std::regex_search` (`:805`/`:828`, substring match, first match wins); unpinned tensors get the ftype mixture; then the fallback. Patterns only apply when the ftype's default type is quantized. |
| `:933` `static bool tensor_requires_imatrix(` | Stock requires an imatrix for IQ1/IQ2/IQ3_XXS targets and for Q2_K only inside a `Q2_K_S` file. The capsule's own rule (VALIDATION.md) is stricter: name an imatrix below 3.5 bpw. |
| `:1264` `llama_split_path(` with `src/llama.cpp:545` `"%s-%05d-of-%05d.gguf"` | Output shard names with `--keep-split`. |
| `:1315` `bool quantize = cur_type != new_type;` | A tensor pinned to its own type is copied byte for byte. |
| `:1383` `if (ggml_is_quantized(tensor->type) && !params->allow_requantize)` | Requantization guard: NVFP4 -> Q2_K throws without `--allow-requantize`. |
| `:53` `static std::string remap_layer(` | `--prune-layers` renumbers the kept layers above the first pruned one; the probe keeps layers 0..L so names and pins stay valid. |

## Types, kernels, Muse

| Anchor | What it fixes |
| --- | --- |
| `ggml/include/ggml.h:219`-`:263` | Type ids: Q2_K = 10, Q8_0 = 8, BF16 = 30, MXFP4 = 39, NVFP4 = 40, Q1_0 = 41, Q2_0 = 42, F8_E4M3 = 43. |
| `ggml/src/ggml-common.h:226` `} block_nvfp4;` and the `static_assert`s at `:309`-`:460` | Block sizes: NVFP4 36 bytes per 64 values, Q2_K 84 per 256, Q4_K 144 per 256, Q8_0 34 per 32 (`helpers/gguf_pack.py` repeats the table). |
| `ggml/src/ggml-cuda/mmvq.cu:38`-`:60` and `mmq.cu:395` `ggml_cuda_should_use_mmq` | CUDA kernels for Q2_K-Q6_K, Q4_0-Q8_0, IQ2_*, IQ3_*, IQ4_*, IQ1_*, MXFP4, NVFP4. The admitted GB10 list leaves out IQ1_* and Q1_0/Q2_0/TQ* on quality and novelty grounds, not for lack of a kernel. |
| `src/llama-model.cpp:1897` `MoE expert weight scales (per-expert, shape {n_expert})` | Loader creates the `[n_expert]` `ffn_*_exps.scale` tensors; the pack must carry them unchanged. |
| `src/models/muse-spark.cpp:172`-`:183` `build_moe_ffn(... nullptr, nullptr, nullptr, nullptr, nullptr, ...)` | At this pin the Muse graph passes `nullptr` for `up_exps_s`, `gate_exps_s` and `down_exps_s`: the loaded `.scale` tensors are not applied. Judge coherence on the wired engine E0 (the `wire_expert_scales` change), for the NVFP4 and the Q2 pack alike. |
