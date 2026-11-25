# Method: build demand-driven parallel expert fill

The node owes one diff, `change`, checked by `verify` at stage `runtime acceptance`. Keep every command, log and
JSON result with the task. Pass absolute paths. On the shared Spark never run uncapped
(`systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0`), nice every build and run, and use the tiny
packs only: never load a full Muse pack from this method.

## 0. The contract the verifier reads

These names are fixed; everything else (structure, file names, defaults of the other knobs) is yours.

| Item | Contract |
| --- | --- |
| Gate | `LLAMA_EXPERT_FILL=1` turns the fill on; unset or `0` is the stock path. |
| Read-all knob | `LLAMA_EXPERT_FILL_SKIP_RESIDENT=0` reads every selected range even when resident (default 1). The tiny pack is always resident, so this is how verify sees the read pool work. |
| Phase knob | `LLAMA_EXPERT_FILL_MAX_TOKENS=N` fills ubatches of at most N tokens (default 1 = decode only), `0` every ubatch. |
| Marker | exactly one line containing `expert_fill: active` per context when the gate is set; no line containing `expert_fill` when unset. |
| Stats | at context teardown, one line `expert_fill: stats k=v ...` with at least `calls` (layers filled), `bytes_read`, `reads` (pread calls), `fill_us`; `read_errors` is checked when present. |

Log them with `LLAMA_LOG_INFO`: llama-simple shows them by default, llama-server and llama-perplexity at `-lv 4`.

## 1. Read the tree

Use SOURCE-MAP.md as a guide and confirm each anchor with `git grep` in your checkout: where the router output
is named (`cb(selected_experts, "ffn_moe_topk", il)` in `build_moe_ffn`), how the scheduler calls an eval
callback (`ggml_backend_sched_compute_splits`), where `cparams.cb_eval` is installed (`process_ubatch`), how
expert tensors land in the mapping (`load_all_data`: `->data` points into the mmap for host buffers), and the
existing `sched_copy_experts` (the same id-scan pattern, for device uploads).

## 2. Choose the hook

The low-risk hook at 9048bad8 is the eval callback on `ffn_moe_topk-<il>` (`samples/router_hook.cpp`): it runs
after routing, before the layer's `MUL_MAT_ID`s, on the main thread, and needs no ggml change. The alternative is
a before-node CPU-split callback in `ggml-backend` (expert_streaming 2.x patch 02); it is allowed by scope but is
a bigger change. Decide and write down why.

## 3. Map ids to file ranges

Per selected id `e` and expert tensor `w` of layer `il` (`ffn_up_exps`, `ffn_gate_exps`, `ffn_down_exps`,
`ffn_gate_up_exps`): `[w->data + e*w->nb[2], w->nb[2])`. Turn the address into (file, offset): either
`/proc/self/maps` (self-contained, `samples/read_pool.h`) or plumb `llama_tensor_weight{idx, offs}` from the
loader into the model (expert_streaming 03 did this; it touches the loader and model). Skip and count ranges
that are not host or not file-backed.

## 4. Read in parallel

`mincore` the page-aligned span; group missing pages into runs; split runs into chunks
(`LLAMA_EXPERT_FILL_CHUNK_KIB`); hand them to a fixed pool (`LLAMA_EXPERT_FILL_THREADS`) that `pread`s into
per-thread scratch buffers; wait for all. Open the file once with your own fd (not the mapping's). Count
everything you report in the stats line.

## 5. Gate the phase

Set a per-ubatch flag in `process_ubatch` before compute: fill only when `n_tokens <= MAX_TOKENS` (default 1).
Prefill reads experts densely and gains little from per-layer fills; keep it stock unless measured.

## 6. Build and self-check (CPU, capped, niced)

```sh
cmake -S TREE -B build-cpu -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF
nice -n 10 cmake --build build-cpu --target llama-simple llama-perplexity -j 8
sh samples/acceptance_run.sh STOCK_BIN build-cpu/bin ~/spike-muse-tiny/gguf/tiny-q2exps.gguf
```

## 7. Verify

```json
{"capability": "verify", "inputs": {"checkout": "/abs/llama.cpp", "diff_path": "/abs/change.diff",
 "tiny_dir": "/abs/spike-muse-tiny/gguf", "work_dir": "/abs/scratch", "jobs": 8}}
```

If the checkout also holds the Muse scale-wiring change uncommitted, commit it (then `base` HEAD), or pass it as
`carried_diff`. Iterate until `done` is true. Then hand the change to the lab for the decode A/B on the real pack
(gate unset vs `LLAMA_EXPERT_FILL=1`, ABBA, untraced); `verify` never claims a speedup.
