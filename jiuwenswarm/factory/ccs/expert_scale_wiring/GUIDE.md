# Expert scale wiring builder: guide for the worker

**Expert scale wiring** is the graph-side part of the weight format toolkit (atlas `weights.format_toolkit`):
the per-expert scale tensors a pack carries (`blk.N.ffn_{gate,up,down}_exps.scale`, F32 `[n_expert]`) must be
applied to the routed expert matmuls, or the NVFP4 blocks are read without their global scale. This capsule is
the method for wiring them into one architecture's MoE block in whatever llama.cpp tree is in front of you. It
ships no finished change.

## What is in the way (stock 9048bad8, Muse Spark)

- The loader already creates `ffn_*_exps_s` (and `_in_s`) for every architecture, `TENSOR_NOT_REQUIRED`: a pack
  without them loads with null pointers.
- `build_moe_ffn` already applies `up_exps_s`, `gate_exps_s`, `down_exps_s` per selected expert when they are
  non-null.
- The Muse graph passes `nullptr` for those arguments. An NVFP4 pack then computes with unscaled blocks: NaN on
  the tiny pack, garbage on the real one. Packs without scales (BF16, IQ2_XXS) are unaffected, and must stay so.

## The change, in words

In the architecture's graph, pass the layer's loaded scale tensors to the matching `build_moe_ffn` parameters.
Nothing else: no new ops, no new switches (absent tensors are the off switch), no edits in ggml or the loader.

## Rules of thumb

1. Bind by parameter name, not by position you remember: the function has overloads and long default tails.
   Read the declaration in `src/llama-graph.h` and count.
2. Up, gate and down each take their **own** scale. Muse RMS-normalizes each expert's output, so a wrong up or
   down scale barely moves the logits; only the per-matmul comparison (expert slice) shows it. Do not rely on
   perplexity alone.
3. Parity first (a scale-free pack must be byte-identical to stock), numerics second (NVFP4 vs the dequantized
   reference: KLD and one layer slice).
4. On GB10 CUDA the default NVFP4 MMQ path quantizes activations to FP4 (tiny-pack KLD ~0.0115 vs ~0.0013 on
   CPU); `GGML_CUDA_MMQ_PREC=q8` gives ~0.0030. Report which you measured; the gate is the CPU run.

## Samples (labelled)

- `samples/bind_by_name.cpp` - how to map a long call to a declaration with parameter-name comments (generic arch).
- `samples/optional_scale_loader.cpp` - the stock loader pattern that makes scale tensors optional (read only).
- `samples/numerics_run.sh` - parity, KLD and layer-slice commands on the tiny packs.

See METHOD.md for the steps, SOURCE-MAP.md for anchors and allowed paths, VALIDATION.md for the gates.
