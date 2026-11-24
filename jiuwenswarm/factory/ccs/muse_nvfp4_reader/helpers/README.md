# Muse NVFP4 reader helpers

| File | Half | Needs | Does |
| --- | --- | --- | --- |
| `scale_inventory.py` | actor (+ `scale_inventory` capability) | stdlib | Role-by-role inventory (packed weight, block scale, global scale, input scale: dtype and shape) from an index and shard headers (local files, `hdr-NNNNN.json`, or `--url` range requests). Also the reference `verify_pack` reads. |
| `tiny_checkpoint.py` | actor + verifier | torch, safetensors | Deterministic 4-layer, 16-expert Muse checkpoints: `bf16/`, `nvfp4/` (ModelOpt layout, 3 shards + index), `deqref/` (F32 dequantized reference). Reproduces the spike's tiny checkpoints byte for byte. |
| `make_tiny_packs.sh` | actor | the venv + a tree with your converter change | Writes the checkpoints and the three tiny packs (`tiny-bf16.gguf`, `tiny-nvfp4-f32.gguf`, `tiny-deqref-f32.gguf`) the scale wiring verifier reads as `tiny_dir`. |
| `time_one_expert.py` | actor | torch, safetensors, the tree | Reads and repacks one expert with the tree's `_nvfp4_pack`, projects the full repack time. |
| `patchlib.py` | verifier | stdlib | Unified diff parser and strict applier (post-images from HEAD). |
| `checkout.py` | verifier | stdlib + git | Reads the candidate from the checkout without writing to it; exports trees with `git archive`; nice + cgroup cap wrapper. |
| `converter_rules.py` | verifier | stdlib | Static gates (VALIDATION.md). |
| `nvfp4_compare.py` | verifier | numpy, torch, safetensors | Runtime gates: GGUF vs checkpoint, block bytes, scales, dequantized weights. |
| `gguf_pack.py` | verifier | stdlib | GGUF v2/v3 header reader (copied from the pack compiler capsule). |
| `pack_census.py` | verifier | stdlib | `verify_pack` checks and the pack manifest. |

The conversion venv: `python3 -m venv .venv && .venv/bin/pip install torch --index-url
https://download.pytorch.org/whl/cpu && .venv/bin/pip install safetensors numpy transformers && .venv/bin/pip
install -e TREE/gguf-py`. The verifier puts the exported tree's `gguf-py` first on the path, so the editable
install may point at any tree.
