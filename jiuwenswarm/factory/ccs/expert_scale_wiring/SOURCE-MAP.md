# llama.cpp source map (graph side)

Anchors checked with `git grep` in stock llama.cpp `9048bad8d6e3a0f9f1726e238e451181c7e02613`. Line numbers are
a guide only; find the names in the tree in front of you.

## Allowed paths

**`src/models/muse-spark.cpp` only.** `verify` fails any other path; `ggml/`, `gguf-py/`, `include/`,
`conversion/`, `common/` and `tools/` are named as protected.

## Edit

| Anchor | Why |
| --- | --- |
| `src/models/muse-spark.cpp` `llama_model_muse_spark::graph::graph`, `build_moe_ffn(` call (`:172`-`:184`) | Passes `nullptr, nullptr, nullptr, nullptr, nullptr` for `gate_up_exps, up_exps_s, gate_exps_s, down_exps_s, selected_experts_in`. The three scale positions take the layer's loaded tensors. |

## Read

| Anchor | What it tells you |
| --- | --- |
| `src/llama-graph.h` `build_moe_ffn(` declarations (`:1196`, `:1219`) | Two overloads. The first (21 parameters, `type_op` 9th) is the one Muse binds; `probs_in, gate_up_exps, up_exps_s, gate_exps_s, down_exps_s, selected_experts_in, post_exp_norm, post_exp_norm_eps` default to null / `1e-5f`. |
| `src/llama-graph.cpp` `build_moe_ffn` definitions (`:2204`, `:2252`), `build_experts` lambda (`:2445`) | `build_lora_mm_id(up_exps, cur, ids, up_exps_s, ...)` (`:2469`), gate (`:2482`), down (`:2594`): the scale is gathered per selected expert and multiplied in; a null scale is skipped. `_scaled` callback names (`ffn_moe_up_scaled`, ...) appear only when a scale is applied. |
| `src/llama-graph.cpp` `build_lora_mm_id` (`:1761`) | Where the per-expert scale multiply happens. |
| `src/llama-model.cpp` `llama_model_base::load_tensors` (`:1708`), "MoE expert weight scales" (`:1897`-`:1906`) and expert input scales (`:1957`-`:1963`) | `ffn_{gate,down,up}_exps_s` / `_in_s` created `{n_expert}` with `TENSOR_NOT_REQUIRED` after the per-arch tensors: absent in a pack means `nullptr`. |
| `src/llama-model.h` `ffn_gate_exps_s`, `ffn_down_exps_s`, `ffn_up_exps_s` (`:364`-`:366`) | The fields you pass. |
| `src/models/muse-spark.cpp` expert tensors (`:73`-`:75`), `ffn_post_exp_norm` (`:71`) | Separate gate/up/down experts (no fused gate_up), and the per-expert post norm that makes up/down scale mistakes nearly invisible in the logits. |
| `examples/eval-callback`, `tools/perplexity` | `llama-eval-callback` (tensor dumps for the layer slice) and `llama-perplexity --kl-divergence-base / --kl-divergence`. |
| `ggml/src/ggml-cuda/mmq.cu:95` `GGML_CUDA_MMQ_PREC` (q4, q8, auto) | GB10: default NVFP4 MMQ uses FP4 activations; `q8` switches to Q8 activations. Read only. |

## Protected (never edit in this node)

`ggml/` (kernels), `src/llama-graph.cpp` / `.h` (shared MoE builder: every architecture), `src/llama-model.cpp`
(loader), `gguf-py/`, `conversion/` (the reader capsule's node).
