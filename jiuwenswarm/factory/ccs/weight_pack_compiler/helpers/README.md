# Pack compiler helpers

Standard library only; run from the capsule directory with any Python 3.10+. Nothing here loads tensor data
except `gguf_pack.read_tensor` on small tensors (the F32 `.scale` tensors).

| File | Half | Does |
| --- | --- | --- |
| `gguf_pack.py` | shared reader | GGUF v2/v3 header reader, shard discovery (`*-00001-of-0000N.gguf`, a directory), census by tensor role, ggml block-size table, raw tensor bytes, pack digest. |
| `recipe.py` | actor | Drafts a `factory.pack-recipe/1` from the census: targets, anchored `--tensor-type` pins, argv, probe argv, byte and disk estimates. CLI: `python helpers/recipe.py FIRST_SHARD --imatrix F --out recipe.json`. |
| `stock_quantize.py` | verifier | The verifier's own model of stock llama-quantize argv parsing and per-tensor type choice (written from the stock source, independent of `recipe.py`). |
| `recipe_check.py` | verifier | `verify_recipe` checks (VALIDATION.md). |
| `pack_check.py` | verifier | `verify_pack` checks and the pack manifest (`factory.pack-manifest/1`). |

Tensor roles (`gguf_pack.role_of`): `routed_expert` is `blk.N.ffn_{gate,up,down,gate_up}_exps.weight`;
`expert_scale` is `*_exps.scale` / `*_exps.input_scale`; then `shared_expert`, `router`, `norm`, `attention`,
`dense_ffn`, `embedding`, `output`, `other`.
