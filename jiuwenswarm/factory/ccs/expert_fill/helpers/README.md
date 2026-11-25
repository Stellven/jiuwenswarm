# Expert fill helpers

Standard library only (Python 3.10+, git, cmake and a C++ toolchain for the build).

| File | Half | Does |
| --- | --- | --- |
| `fill_rules.py` | verifier | Static gates: scope, gate env and default off, fill keyed before the expert matmul, no tensor writes, no graph change. |
| `fill_runs.py` | actor + verifier | Capped, niced `llama-simple` and `llama-perplexity -lv 4` runs with a clean `LLAMA_EXPERT_FILL*` env; parses the `expert_fill: active` marker and the `expert_fill: stats k=v` line. |
| `patchlib.py`, `checkout.py` | verifier | Diff parse/apply, read-only checkout access and tree export, cgroup cap (same files as the scale wiring capsule). |

Tiny pack: `tiny-q2exps.gguf` (Muse tiny, Q2_K experts, mmap-backed on CPU) from `~/spike-muse-tiny/gguf` on
the Spark; any tiny MoE GGUF whose experts are not repacked works (`pack`).
