# Muse NVFP4 reader builder: guide for the worker

The **checkpoint reader** is the part of the converter that reads a checkpoint's tensors and their
quantization planes and hands them to the GGUF writer (atlas: `weights.checkpoint_reader`). This capsule is
the method for extending the stock llama.cpp converter so it reads the official Muse Spark Open NVFP4
checkpoint (ModelOpt layout) and writes an NVFP4 GGUF pack. It ships no finished converter change: you
inspect the checkpoint, then write the change into whatever llama.cpp tree is in front of you.

## What is in the way (stock 9048bad8)

- Muse stores routed experts **stacked**: one `experts.gate_up_proj` per layer, U8 `[E, 2*I, M/2]` (gate rows
  first, then up), with `_weight_scale` (F8_E4M3, one per 16 values), `_weight_scale_2` (F32 `[E, 2]`: column
  0 for gate, column 1 for up, **not shared**) and `_input_scale` (F32 `[E, 2]`); `experts.down_proj` likewise
  with `[E]` scale vectors. Layers 0 and 61, attention, latent projections and lm_head are BF16; the router F32.
- The stock NVFP4 reader (`_generate_nvfp4_tensors`) only matches per-expert `*.weight` + `*.weight_scale`.
  The stacked U8 tensors pass through as "uint8 -> BF16" garbage, then mapping `..._weight_scale_2` fails.

## Parts of the change

- **Stacked expert reader** - in the Muse model class, extend the NVFP4 hook so stacked experts with a
  `_weight_scale` are split per projection (gate rows `[0, I)`, up rows `[I, 2I)`, down whole), repacked per
  expert with the stock `_nvfp4_pack` (bits move, nothing is requantized) and written as ggml NVFP4 (type 40).
- **Scale planes** - one `[E]` F32 `.scale` per routed expert weight from `_weight_scale_2` (gate column 0, up
  column 1, down the vector) and the matching `.input_scale`. The graph applies `.scale` at run time.
- **Lazy writer** - the GGUF writer keeps every added tensor until the final write. Wrap each repacked stacked
  tensor in a `gguf.LazyNumpyTensor` (as the stock MXFP4 builder does) so only the tensor being written is
  resident. Eager repacking holds ~435 GB on the real checkpoint.
- **Excluded modules** - stacked experts without `_weight_scale` stay at their stored type and take the stock path.

## Rules of thumb

1. Inspect before you write: index + one shard header, role by role (`helpers/scale_inventory.py`).
2. Reuse stock pieces (`_nvfp4_pack`, `_write_scales_tensor`, `_tag_prec_a4`, `LazyNumpyTensor`); edit only
   `conversion/*.py`. Never touch `gguf-py/` or `src/` here (the graph is the next node's job).
3. Prove it on the tiny checkpoint first (`helpers/tiny_checkpoint.py`): conversion takes seconds there.
4. Time one expert, project, then run the full conversion capped, niced, split.
5. Every number you report is a measurement with its command and log.

## Samples (labelled, not the answer)

- `samples/range_header.py` - read a safetensors header from a URL (range request) or a local shard.
- `samples/split_stacked.py` - split a stacked `[E, 2I, ...]` tensor and an `[E, 2]` scale by rows and columns.
- `samples/lazy_expert_tensor.py` - the deferred-load pattern with `gguf.LazyNumpyTensor`.

See METHOD.md for the steps, SOURCE-MAP.md for anchors and allowed paths, VALIDATION.md for the gates.
