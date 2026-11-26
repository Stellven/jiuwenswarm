# Method: extend the converter to read Muse NVFP4 and write the pack

The node (`ingest_nvfp4`) owes a **converter** diff (checked by `verify`) and an **NVFP4 pack** (checked by
`verify_pack`). Run the steps in order; keep every command, log and JSON result with the task. Pass absolute
paths to every capability. On the shared Spark never load or convert uncapped.

## 1. Inspect the checkpoint (headers only)

Read the index and at least one shard header that holds a quantized layer's experts, and one that holds an
excluded layer's. A header is 8 bytes of little-endian length plus JSON; it costs KiB, not GB.

```sh
python helpers/scale_inventory.py /models/muse-nvfp4/model.safetensors.index.json \
    --headers /models/muse-nvfp4/model-00005-of-00127.safetensors /models/muse-nvfp4/model-00093-of-00127.safetensors \
    --out /work/inventory.json
# not downloaded yet: --url https://huggingface.co/<repo>/resolve/main --shards 3,5,93 (two range requests each)
```

or call the `scale_inventory` capability. Read `roles` and `findings` and write down, per role: packed weight
(dtype, shape), block scale, global scale (`_weight_scale_2`: `[E, 2]` or `[E]`?), input scale; which layers are
quantized and which excluded (`hf_quant_config.json` `exclude_modules`). The `pin_inputs` node records this.
`verify_pack` later reads the checkpoint itself (index, headers, scale_2 values), not this JSON.

## 2. Read the stock reader in your tree

Open `conversion/base.py` (SOURCE-MAP.md): `_generate_nvfp4_tensors` (what it matches and what it drops),
`_nvfp4_pack` (the bit move), `_flush_nvfp4_experts` and `_write_scales_tensor` (how per-expert scales become an
`[E]` tensor), `_mxfp4_expert_tensor` (the lazy builder to imitate). Then `conversion/muse_spark.py`: how the
BF16 path splits `gate_up_proj` (gate first) and names the outputs. Confirm against your inventory; if the tree
differs from this map, the tree wins.

## 3. Write the change (conversion/*.py only)

In the Muse model class, override the NVFP4 hook to take the stacked experts that have a `_weight_scale` out of
`model_tensors` before the stock pass, and for each projection:

- split rows: gate `[0, I)`, up `[I, 2I)`; down whole; pair each with the same rows of the block scale;
- repack each expert with the stock `_nvfp4_pack` inside a function handed to `gguf.LazyNumpyTensor` (meta
  shape `(E, rows, in/64*36)` uint8), add it with `raw_dtype=NVFP4`, tag precision like the stock path;
- write `.scale` from `_weight_scale_2` (gate column 0, up column 1, down the vector) and `.input_scale`
  likewise. Small `[E]` vectors may be loaded eagerly; the packed weights must not;
- leave stacked experts without `_weight_scale` (excluded layers) to the stock BF16 path, then call the stock hook
  for everything else.

Samples: `samples/split_stacked.py`, `samples/lazy_expert_tensor.py`.

## 4. Prove it on the tiny checkpoint

```sh
PY=/path/to/venv/bin/python          # torch (cpu), safetensors, numpy, transformers; pip install -e TREE/gguf-py
$PY helpers/tiny_checkpoint.py --out /work/tiny/ckpt --tokenizer-dir /models/muse-ref --config /models/muse-ref/config.json
$PY TREE/convert_hf_to_gguf.py /work/tiny/ckpt/nvfp4 --outfile /work/tiny/tiny-nvfp4.gguf --outtype bf16
```

Then call `verify` on your diff with `python` and `tiny_checkpoint` (or `tiny_base`). Runtime acceptance is
the bar: without `python` or a tiny checkpoint, `verify` fails at that stage, and a static rule that is
`inconclusive` (a split it cannot read) is never a pass on its own. The runtime checks compare every NVFP4
block with the source bits, every `.scale` with its scale_2 column, and the dequantized weights with the
checkpoint's own dequantization. `helpers/make_tiny_packs.sh` also writes the three tiny packs the next node
(`wire_expert_scales`) needs and `tiny-packs.sha256.json` (sha256 per pack) that pins them for its verifier.

**Shared checkout.** `verify` judges only this node's change: `conversion/*.py`. If the checkout also holds
another node's uncommitted change (for example the graph edit in `src/models/muse-spark.cpp`), carry it one of
these ways, or `allowed_paths` fails: commit it first (then it is in `base`, default HEAD); or pass
`diff_path` with only your change; or pass `carried_diff` with the other node's patch (files equal to base plus
that patch are exported but not reviewed). Hand your own change on the same way: commit it, or give the next
node its patch as `carried_diff`.

## 5. Time one expert, project

```sh
$PY helpers/time_one_expert.py --checkpoint /models/muse-nvfp4 --tree TREE --layer 1
```

It reads one expert of layer 1 (gate_up and down) through a safetensors slice and repacks it with your tree's
packer. Projected total = per-expert seconds x experts x quantized layers; add the write time. Print and record
the projection before the full run; if it does not fit the node's time limit, stop and report it.

## 6. Full conversion: lazy, capped, niced, split

```sh
systemd-run --user --scope -p MemoryMax=96G -p MemorySwapMax=0 \
  nice -n 10 ionice -c3 $PY TREE/convert_hf_to_gguf.py /models/muse-nvfp4 \
    --outfile /packs/muse-nvfp4/muse-nvfp4.gguf --outtype bf16 --split-max-size 50G 2>&1 | tee /work/convert.log
```

96 GiB is the cap the real conversion needed, and your reader does not set that peak: the excluded layers 0
and 61 go through the stock BF16 path, which holds a whole stacked `gate_up_proj` (BF16 [256, 8192, 4096],
16 GiB, more while it is split and cast). The real runs capped at 32 and 64 GiB were OOM-killed there, at
layer 0's experts. So a kill at a lower cap does not by itself say your writer is eager. Laziness is shown by
the one-expert timing probe (step 5: one expert read through a slice, never the stacked tensor) and by RSS
growth during the run: across the NVFP4 layers (1-60) RSS stays flat from layer to layer, near one stacked
tensor plus overhead. If RSS climbs layer by layer there, the writer is holding repacked experts: stop and fix
the change (the `lazy_repack` rule names eager loads), do not raise the cap. Watch RSS
(`systemctl --user status`) and disk. The log must show
every quantized layer's `ffn_{gate,up,down}_exps` repacked as NVFP4 with `+ ... (per-expert scale, shape [256])`
lines, and no `uint8 --> BF16` line.

## 7. verify_pack, then hand off

Call `verify_pack` with the first shard, `source_index` (the checkpoint's `model.safetensors.index.json`, with
the shards beside it), the byte range and `hash: true` (allow for hashing ~450 GB; or hash once in a separate
step). The layer plan, the excluded layers' dtypes and the expected `.scale` values all come from the
checkpoint: the index, the shard headers and one small range read per `_weight_scale_2`. Your inventory, if
passed, is only cross-checked. It returns the pack manifest (`factory.pack-manifest/1`)
that `requant_q2` and the evidence record name. Hand the pack and the three tiny packs to `wire_expert_scales`.

For read-only input pinning use `inspect_scale_layout` with the checkpoint index and shard headers. Its receipt includes the scale inventory.
