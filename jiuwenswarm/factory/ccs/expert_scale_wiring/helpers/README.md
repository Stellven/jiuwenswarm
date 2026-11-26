# Expert scale wiring helpers

Standard library only (Python 3.10+, git, cmake and a C++ toolchain for the build).

| File | Half | Does |
| --- | --- | --- |
| `parity.sh` | actor | Greedy `llama-simple` on a scale-free pack with stock and candidate binaries, capped and niced; byte compare. |
| `kld_compare.py` | actor + verifier | `llama-perplexity --kl-divergence-base` on the reference, `--kl-divergence` on the model; parses mean KLD, PPL(Q), PPL(base), same top p. |
| `slice_compare.py` | actor + verifier | Compares one layer of two `llama-eval-callback` dumps: expert matmuls (gate, up, down; `_scaled` names matched to unscaled) and block output, max abs diff over max abs reference. |
| `wiring_rules.py` | verifier | Static gates: scope, the `build_moe_ffn` call bound to its declaration by parameter name, scale arguments, nothing else moved. |
| `patchlib.py`, `checkout.py`, `gguf_pack.py` | verifier | Diff parse/apply, read-only checkout access and tree export, GGUF header census (same files as the reader capsule). |

The tiny packs (`tiny-bf16.gguf` without scales, `tiny-nvfp4-f32.gguf`, `tiny-deqref-f32.gguf`) come from
`weights.build_muse_nvfp4_reader` (`helpers/make_tiny_packs.sh`) and a tree with its converter change.
