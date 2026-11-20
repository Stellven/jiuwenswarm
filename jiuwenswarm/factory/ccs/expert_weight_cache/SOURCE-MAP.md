# llama.cpp source map

Anchors were checked with grep in `~/predemo/llama.cpp-stock` at
`9048bad8d6e3a0f9f1726e238e451181c7e02613`.

| Access | Stock file and anchor | Purpose |
| --- | --- | --- |
| Edit | `src/llama-context.cpp:609`, native cache construction | Use the `cparams.moe_cache_size` guard, including configurations in which stock has no cacheable slices. |
| Edit | `src/llama-context.cpp:633`, `llama_context::~llama_context`; `:955`, `llama_context::synchronize` | Retire outstanding leases only after scheduler synchronization. Emit final stats while cache and backends are live. |
| Read | `src/llama-context.cpp:782`, `ggml_backend_sched_set_copy_callback` registration | Existing context callback carries the context as user data. |
| Edit | `src/llama-context.cpp:3128`, `llama_context::graph_compute`; `:3159`, `llama_context::sched_copy_experts` | Scope the operation and wrap the stock selected-expert copy. Preserve native cache precedence, ID-derived selection at `:3174`, and stock padding at `:3231`. |
| Edit | `src/llama-context.h:317`, `sched_copy_experts`; `:347`, `moe_cache`; `:427`, `copy_experts` | Context callback and existing cache/copy state next to the proposed owned state. |
| Read | `src/llama-model.cpp:1708`, `llama_model_base::load_tensors`; `:1720`, auto-mode resolution; `:1747`, effective mode log; `:2082–2085`, mapping-backed buffer; `:2184`, retained mappings; `src/llama-model.h:786`, `llama_model` | Distinguish effective mode and mapping-backed buffers from copied host tensors. Leave model files read-only. |
| Read | `src/llama-mmap.h:56` and `:57`, `llama_mmap::size` and `addr` declarations | Establish mapping bounds for exact source ranges. |
| Read | `src/llama-moe-cache.cpp:881`, constructor; `:965`, `llama_moe_cache::copy`; `:969`, `llama_moe_cache::copy_experts` | Understand the bypass path that retains native cache behavior. |
| Edit | `src/CMakeLists.txt:17`, source list; `:70`, C++17 | Register the new cache unit with the existing target. |
| Read | `ggml/src/ggml-backend.cpp:461`, `ggml_backend_tensor_set_async`; `:908`, `ggml_backend_tensor_copy_async`; `:2100`, `ggml_backend_sched_copy_input`; `:2213`, `ggml_backend_sched_compute_splits`; `:2490`, `ggml_backend_sched_synchronize` | Check backend copy behavior, stock schedule ordering, slot reuse, and the completion boundary. |
| Read | `ggml/include/ggml-backend.h:85`, `ggml_backend_alloc_buffer`; `:469`, `ggml_backend_tensor_alloc`; `:470`, `ggml_backend_view_init` | Allocate staged bytes and assess valid copy view construction. |
| Read | `src/llama-impl.h:28`, `LLAMA_LOG_INFO` | Use the stock INFO log level. |
| Read | `common/arg.cpp:2666` and `:2677`, mmap option; `:2752`, `--moe-cache-mib` | Existing operator controls for mapped loading and native cache. `:3994` defines log verbosity. |
| Protected | `src/llama-graph.cpp:2375`, `ffn_moe_topk`; `src/llama-sampler.cpp:896`, `llama_sampler_sample` | Preserve authoritative selection and token sampling. |

Proposed fresh files are `src/llama-expert-weight-cache.cpp` and
`src/llama-expert-weight-cache.h`. `src/llama-expert-fill.h` may be revised
if already present in the owned checkout. These files have no stock anchors.
The stock scheduler's callback and loader anchors above are the starting
points. An existing Fill implementation in the owned tree may supply mapping
and readiness metadata. Verify its ownership and range semantics before reuse.

## High-churn files

| Stock files | Upstream activity |
| --- | --- |
| `src/llama-moe-cache.cpp`, `src/llama-moe-cache.h` | Seven edits from 2026-10-07 through 2026-11-13. Latest supplied revision `951d465f5` (2026-11-13). |
| `ggml/src/ggml-backend.cpp`, `ggml/include/ggml-backend.h` | GGML backend revision `c56be864f` (2026-11-14). |
| `src/llama-context.cpp`, `src/llama-context.h` | Scheduler copy-experts callback `sched_copy_experts`, `6753a033f0` (2026-10-06). |

Prefer additive, local hooks. Observe through existing scheduler callbacks and
public queries. Wrap stock functions, add an overload that preserves the
existing signature, or add a new file. When none of these approaches works,
stay within the work order's source authority, make the smallest additive diff,
and name the file and explain the reason in the final report. The verifier
reports likely existing signature replacements as informational findings.

## Spark activation profile provenance

The Spark profile derives from the pinned llama.cpp stock CLI and model loaders,
selected Satay round-1/2 implementation evidence, and observed Spark strict-A
startup settings. Its acceptance counters and comparison flags are specified in
[SPARK-PROFILE.md](SPARK-PROFILE.md).

## Profile-driven Spark treatment provenance

[PROFILE-RESIDENCY.md](PROFILE-RESIDENCY.md) uses the frozen Strata profile and retained routing analyses. Strata source pin `ffa80d73133ea5c548aefe57889a16e8085a938f`, `docs/DEEPSEEK41.md` and `setup.py` describe resident experts and layer-major prefill. Pinned llama.cpp `9048bad8d6e3a0f9f1726e238e451181c7e02613`, `src/llama-context.cpp::sched_copy_experts`, `src/llama-moe-cache.cpp::build_lookup`, `src/llama-model-loader.cpp` tensor overrides and the CUDA offload threshold distinguish the available transfer paths. The observed C1 prefill-only copy profile is evidence for measurement design.
# Native profile source

At stock `9048bad8d6e3a0f9f1726e238e451181c7e02613`, the native bank in
`src/llama-moe-cache.cpp` allocates group projections, manages `moe_cache_lru`,
and reports ordinary refill and large-batch copy counters. Its `get_slot_map`
lookup cutoff is separate from `copy_experts`, which `src/llama-context.cpp`
uses for selected large-prefill copies into scheduler destinations. This is
the bank reused by the opt-in method in [NATIVE-PROFILE.md](NATIVE-PROFILE.md).
The relevant experimental inputs include the complete C1 v2 report, exact
positive-upload residency counterfactual, and the retained A+ calibration
decode-fault report. The latter does not measure fixed-prompt TTFT. Stock
native replay at three cache sizes is a routing simulation. The planner
records their exact artifact and release identities in its own decision.

## Iteration-2 prefill evidence

Pinned stock `9048bad8d6e3a0f9f1726e238e451181c7e02613` implements contiguous large-prefill native D2D in `src/llama-moe-cache.cpp` and host misses and MMQ tail source handling in `src/llama-context.cpp`. The native profile candidate `ad2130b0126ad0c8f7ac33d966f828fc17f4528c` adds seed and phase counters. [PREFILL-HITS.md](PREFILL-HITS.md) uses actual C3/S/A and mincore evidence to bound the next source choices.
