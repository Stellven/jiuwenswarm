# llama.cpp source map (expert fill)

Anchors checked with `git grep` in stock llama.cpp `9048bad8d6e3a0f9f1726e238e451181c7e02613` (b12493). Line
numbers are a guide only; find the names in the tree in front of you. The expert_streaming capsule's
SOURCE-MAP.md maps the same mechanism on an older base (`cf34d3113`, Qwen3.6-A3B); read it for the ideas, not
the line numbers, and note its fill needed a new scheduler hook and loader plumbing that this base does not.

## Allowed paths

`verify` fails any path outside this set:

| Path | For |
| --- | --- |
| `src/llama-context.cpp`, `src/llama-context.h` | the gate, the hook, the per-ubatch phase flag, the stats line |
| `src/llama-expert-fill.h`, `src/llama-expert-fill.cpp` (+ `src/CMakeLists.txt` to list the .cpp) | the read pool, residency probe, address lookup |
| `src/llama-cparams.h` | a cparams field if you carry the config there |
| `src/llama-mmap.{h,cpp}`, `src/llama-model.{h,cpp}`, `src/llama-model-loader.{h,cpp}` | loader plumbing of file offsets or fds, mapping advice (optional route) |
| `ggml/include/ggml-backend.h`, `ggml/src/ggml-backend.cpp` | a before-node scheduler hook (optional route) |

Protected (named failures): `ggml/src/ggml-cpu/`, `ggml/src/ggml-cuda/` (kernels), `src/models/` (model graphs,
including the Muse scale wiring node's file), `src/llama-graph.{h,cpp}` (shared MoE builder), `gguf-py/`,
`conversion/`, `include/llama.h` (public API).

## Read

| Anchor | What it tells you |
| --- | --- |
| `src/llama-graph.cpp:2375` `cb(selected_experts, "ffn_moe_topk", il)` in `build_moe_ffn` | The router output, I32 `[n_expert_used, n_tokens]`, a strided view of `ggml_argsort` (`ggml_argsort_top_k`, `ggml/src/ggml.c`). Named `ffn_moe_topk-<il>`. Group-limited routing (`n_expert_groups > 1`) still ends here. |
| `ggml/src/ggml-backend.cpp:2213` `ggml_backend_sched_compute_splits`, `:2263`-`:2283` | With an eval callback: ask per node, compute `[j0, j1]` up to the wanted node, synchronize, call with `ask=false` **after** the node. Returning false stops the graph. Without a callback the split is computed whole. |
| `src/llama-context.cpp:230` `cparams.cb_eval = params.cb_eval` | Where to chain your callback in front of the user's. |
| `src/llama-context.cpp:1817` `process_ubatch`, `:1847` `ggml_backend_sched_set_eval_callback` | The callback is installed when a graph is (re)built; a reused graph keeps it. Set the per-ubatch phase flag at the top of `process_ubatch`. |
| `src/llama-context.cpp:3159` `sched_copy_experts` | Stock pattern for scanning ids of a `MUL_MAT_ID` (device uploads of used experts); not the fill, but the same id handling. |
| `src/llama-model-loader.cpp:1820` `ggml_backend_tensor_alloc(buf_mmap, cur, data)` | Host expert tensors in a mmap buffer: `->data` is `mapping->addr() + offs`. The mapping covers the whole file from offset 0. |
| `src/llama-model-loader.h:32` `llama_tensor_weight` | `{idx, offs}` per tensor: the file and offset, if you plumb instead of reading `/proc/self/maps`. |
| `src/llama-mmap.cpp:718` `POSIX_FADV_SEQUENTIAL`, `MAP_POPULATE` | Stock mapping advice: sequential readahead, populate at load when there are no lazy ranges. Your own fd is unaffected by the mapping's fadvise. |
| `common/common.h:1287` `LLM_FFN_EXPS_REGEX`, `llm_ffn_exps_cpu_override` | `--cpu-moe` puts `ffn_{up,down,gate,gate_up}_exps` on the plain CPU buffer type: mmap-backed, not repacked. |
| `ggml/src/ggml-cpu/ggml-cpu.c:1566` `ggml_compute_forward_mul_mat_id` | Reads only used experts' rows straight from `src0->data`; each missing page is a synchronous major fault on a compute thread. Read only. |
| `src/llama-moe-cache.cpp`, `--moe-cache-mib` | The MoE cache keeps hot experts in its own slots; the fill only helps the misses read from the mapping. Read only. |

## Where the fixtures came from

`tests/fixtures/stock/src/llama-context.{h,cpp}` are the stock 9048bad8 files the static-rule tests apply the
fixture diffs to. `tests/fixtures/good.diff` (llama-context.{h,cpp} + new `src/llama-expert-fill.h`, 403
added lines) passed the full verify on the Spark on 2026-11-25; it calibrates the verifier and is not the method.
