# Method: wire the per-expert scales into the MoE block

The node (`wire_expert_scales`) owes one diff, `change`, checked by `verify` at stage `runtime acceptance`.
Keep every command, log and JSON result with the task. Pass absolute paths. On the shared Spark never run
uncapped (`systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0`), and nice every build and run.

## 1. Find the call

In `src/models/<arch>.cpp` (Muse: `src/models/muse-spark.cpp`) find the graph's `build_moe_ffn(` call. Note the
arguments it passes today, in order.

## 2. Read the signature

In `src/llama-graph.h` find the `build_moe_ffn` declarations. Decide which overload the call binds to (argument
count and types: the overload with separate biases takes `ggml_tensor *` where the other takes
`llm_ffn_op_type`). Write the parameter name next to each argument (`samples/bind_by_name.cpp`). The scale
parameters are `up_exps_s`, `gate_exps_s`, `down_exps_s`; note what precedes them (`probs_in`,
`gate_up_exps`) and follows (`selected_experts_in`, `post_exp_norm`, `post_exp_norm_eps`).

## 3. Confirm the tensors exist and are optional

In `src/llama-model.cpp` (`llama_model_base::load_tensors`, the "MoE expert weight scales" block) confirm
`layer.ffn_{gate,up,down}_exps_s` are created with `TENSOR_NOT_REQUIRED` for any layer that has the expert
weights; `src/llama-model.h` declares the fields. Then a pack without `.scale` tensors keeps `nullptr` and the
graph is the stock graph. Read `src/llama-graph.cpp` `build_moe_ffn`: where each scale is applied
(`build_lora_mm_id(..., up_exps_s, ...)`, `gate_exps_s`, `down_exps_s`) and that a null scale is a no-op.

## 4. Edit

Pass `model.layers[il].ffn_up_exps_s`, `...ffn_gate_exps_s`, `...ffn_down_exps_s` at those three parameters.
Change nothing else in the call or the file. Touch only `src/models/<arch>.cpp`.

## 5. Build (CPU, capped, niced)

```sh
cmake -S TREE -B build-cpu -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF
nice -n 10 cmake --build build-cpu --target llama-simple llama-perplexity llama-eval-callback -j 8
```

Build stock HEAD the same way (or reuse a stock build of the same commit) for parity.

## 6. Parity on a scale-free pack

`helpers/parity.sh STOCK/bin CAND/bin tiny/tiny-bf16.gguf`: greedy stdout must be byte-identical. Check first
that the pack really has no `_exps.scale` tensor. The tiny packs come from the reader capsule
(`weights.build_muse_nvfp4_reader`: `helpers/make_tiny_packs.sh`).

## 7. Numerics on the NVFP4 tiny pack

```sh
python helpers/kld_compare.py --bin CAND/bin --ref tiny/tiny-deqref-f32.gguf --model tiny/tiny-nvfp4-f32.gguf \
    --text TREE/README.md --work /work/kld --threads 8           # mean KLD; spike: 0.0013 (stock graph: NaN)
CAND/bin/llama-eval-callback -m tiny/tiny-nvfp4-f32.gguf -p "The capital of France is" -n 1 > cb-nvfp4.log 2>&1
CAND/bin/llama-eval-callback -m tiny/tiny-deqref-f32.gguf -p "The capital of France is" -n 1 > cb-ref.log 2>&1
python helpers/slice_compare.py cb-nvfp4.log cb-ref.log --layer 1   # expert matmuls + block output, < 0.05
```

The slice comparison is the one that sees a wrong up or down scale (the block's per-expert RMS norm hides it
from KLD). If you also measure on CUDA, record the MMQ activation path: default FP4 activations, or
`GGML_CUDA_MMQ_PREC=q8`.

## 8. verify

Call `verify` with `tiny_dir` (holding `tiny-bf16.gguf`, `tiny-nvfp4-f32.gguf`, `tiny-deqref-f32.gguf`),
`work_dir` outside the checkout, `jobs`, and `stock_bin` if you already built stock (else the verifier builds
and caches stock HEAD in `work_dir`). It reaches `runtime acceptance` only when parity, KLD, no-NaN and the
layer slice all ran and passed.
