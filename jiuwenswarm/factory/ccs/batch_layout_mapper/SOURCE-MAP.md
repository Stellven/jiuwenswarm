# Source map

Stock anchors verified in `~/predemo/llama.cpp-stock` at
`9048bad8d6e3a0f9f1726e238e451181c7e02613`. Line numbers refer to that stock checkout.

| File and anchor | Use |
|---|---|
| `tools/server/server-context.cpp:184`, `server_batch::add`; `216`, `server_batch::size`; `498` and `503`, `server_slot::need_embd` and `server_slot::can_split` | Read. Stock row accounting and eligibility checks. |
| `tools/server/server-context.cpp:1024`, `server_context_impl`, destructor at `1064` | Touch. Hold the gate and fixed counters in the server context. Flush stats at orderly destruction. |
| `tools/server/server-context.cpp:3704`, `server_context_impl::pre_decode`; effective `llama_n_batch` and `llama_n_ubatch` at `3915` and `3916` | Touch. Establish the single-slot prefill hook and read reserved limits. |
| `tools/server/server-context.cpp:4049`, `get_common_prefix`; `4235`, replay of the final token; `4241`, `n_prompt_cached`; `4246`, `keep_first` | Read. Use the post-cache prefix accounting. |
| `tools/server/server-context.cpp:4310`, checkpoint eligibility; `4383`, prompt packing; `4411`, `batch.add`; `4454`, rows appended | Touch the packing bound and observe the resulting span. Reuse stock positions, output flags and row order. |
| `tools/server/server-context.cpp:3483`, `server_context_impl::update_slots`; `4577`, `server_context_impl::decode`; `4612`, `llama_process` | Read. Stock slicing, dispatch and KV retry boundary. |
| `src/llama-context.cpp:350`, effective causal batch limit; `352`, microbatch limit; `788`, `llama_context::sched_reserve`; `802`, reserved row count | Read. Existing compute-buffer ceiling. |
| `src/llama-context.cpp:2140`, `llama_context::decode`; `2256`, `memory->init_batch`; `4620` and `4624`, public batch accessors; `4679`, `llama_get_causal_attn` | Read. Physical microbatch sizing and effective settings. |
| `src/llama-kv-cache.cpp:741`, `llama_kv_cache::init_batch`; `750`, `split_simple` for a single stream; `src/llama-batch.cpp:625`, `llama_batch_allocr::split_simple` | Read. Consecutive stock partitioning for ordinary single-stream attention. |
| `tools/server/server-context.cpp:1495`, configured parallel slots; `3910`, sampled/drafted row collection | Read. Check configured slot count and reject a nonempty pending batch. |
| `common/log.h:131`, `LOG_INFV`; `common/arg.cpp:3994`, `-lv` | Read. Use the verbosity argument 4 for the mapper's INFO records. |
| `common/arg.cpp:2666`, `-lm`; `src/llama-model.cpp:1720`, automatic mmap selection; `1747`, `load_tensors` effective load-mode log | Read. Check mmap-dependent runs against the effective mode. |
| `tools/server/server-task.cpp:332`, `server_task_result_cmpl_final::to_json_non_oaicompat` | Read. Native completion exposes content, tokens, stop type and cached-token counts. |
| `src/llama-batch-layout.h` | New header. Gate read and integer cap calculation. No stock line anchor. |

The earlier `engine.prompt_batch_layout` 1.0.1 targets a different pin. Its mixed-slot divergence informs the single-configured-slot guard.

## Spark activation profile provenance

The Spark profile derives from the pinned llama.cpp stock CLI and model loaders,
selected Satay round-1/2 implementation evidence, and observed Spark strict-A
startup settings. Its acceptance counters and comparison flags are specified in
[SPARK-PROFILE.md](SPARK-PROFILE.md).

## aLoRA transition provenance

At the pinned llama.cpp source `9048bad8d6e3a0f9f1726e238e451181c7e02613`, `tools/server/server-context.cpp` initializes and resets `server_batch.alora_scale` to `-1.0f` and uses `> 0.0f` to restore an adapter and preserve the activation cut. The initial C5 Spark LAB retained no changed-cut records despite the configured active marker. [ALORA-STATE.md](ALORA-STATE.md) describes the state-correct admission.
