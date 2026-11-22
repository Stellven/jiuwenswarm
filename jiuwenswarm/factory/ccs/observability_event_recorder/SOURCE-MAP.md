# llama.cpp source map

Verified against the local stock checkout at `9048bad8d6e3a0f9f1726e238e451181c7e02613`. Line numbers refer to the pinned stock source. Follow symbols if an owned integration has shifted them.

| Stock file and anchor | Use |
| --- | --- |
| `src/CMakeLists.txt:17`, `:68–70` | Add `llama-event-recorder.cpp` to the library source list. The stock library uses C++17. |
| `src/llama-context.h:45`, `:317`, `:414–427` | Add private context state for joining recorder observations. Keep it separate from stock copy state. |
| `src/llama-context.cpp:633` (`~llama_context`), `:782–783` (copy/reallocation callback registration) | Release per-context state after its observations are committed. Register the observers after scheduler creation and preserve existing callbacks. |
| `src/llama-context.cpp:1817` (`process_ubatch`), `:1847`, `:1880`, `:2367` | Bind the active ubatch and wrap the caller's eval callback. Check both graph build and reuse. Finalize the join after the compute submission result. |
| `src/llama-context.cpp:3128` (`graph_compute`), `:3149` | Identify the scheduler submission that owns the current microbatch. |
| `src/llama-context.cpp:3159` (`sched_copy_experts`), `:3163`, `:3223–3234` | Observe actual submitted byte counts, including padding. The native cache can consume the callback before the uncached branch. |
| `src/llama-context.cpp:3243–3248` (`graph_get_cb`) | Read how graph callback labels become `<name>-<layer>`. |
| `src/llama-batch.cpp:906` (`llama_batch_allocr::ubatch_add`), `:947`; `src/llama-batch.h:17`, `:78` | Read the original batch row mapping and ubatch shape. Carry phase and request metadata across stock splitting. |
| `src/llama-graph.cpp:2252` (`llm_graph_context::build_moe_ffn`), `:2375`, `:2451–2483`, `:2596`; `src/models/kolibri1.cpp:132` | Read the selected-expert and consumer labels and check the target architecture's routed paths. Observe selection before any cache-slot remapping. |
| `ggml/include/ggml-backend.h:96`, `:326–333`, `:388–394` | Read tensor data and the eval/copy callback protocol. Read the available observation interfaces before considering an authorized scheduler extension. |
| `ggml/src/ggml-backend.cpp:2100` (`ggml_backend_sched_copy_input`), `:2134–2148` | Identify the fallback when the specialized callback declines. Verify whether the contract exercises it and count only the executed branch. |
| `ggml/src/ggml-backend.cpp:2213` (`ggml_backend_sched_compute_splits`), `:2252–2286` | Inspect copy and compute ordering. The ask notification tests interest, while the read notification follows computation and synchronization. An ask notification alone does not establish readiness. |
| `ggml/src/ggml-backend.cpp:2503` (`ggml_backend_sched_set_eval_callback`), `:2509` (`ggml_backend_sched_set_copy_callback`) | Keep the current callback API and attach observation state separately. |
| `tools/server/server-context.cpp:152–160` (`server_batch::token`), `:4577` (`server_context_impl::decode`), `:4611–4616`, `:5029` (`metrics_post_decode`), `:5046` | Use the existing task/slot and per-row `is_prompt` metadata. Scope tags inside the dispatch callback. Keep the existing batch, API call, synchronization and sampling intact. |
| `tools/server/CMakeLists.txt:38–41`; `include/llama.h:16–26` | Read the existing project include path and symbol visibility conventions for the internal recorder header shared with the server. |
| `src/llama-moe-cache.h:61`; `src/llama-moe-cache.cpp:732` (`copy_experts`), `:759–762`, `:767` (`copy`), `:846–859` | Read cache-hit, fill and metadata copy boundaries. Instrument only if the contract enables the native cache. Account expert-weight payload separately from cache metadata. |
| `src/llama-impl.h:28`; `common/arg.cpp:3994`; `common/log.cpp:551` | Use the existing library INFO macro and set `-lv 4` to see it at runtime. |
| `src/llama-model.cpp:1720–1748`; `common/arg.cpp:2668–2680` | Inspect how auto resolves and find the effective load mode in the `load_tensors` INFO line. |

The verifier recognizes proposed recorder units at `src/llama-event-recorder.h` and `src/llama-event-recorder.cpp`. Its path allowlist matches the component spec. Work Order 1 limits edits to the authorized `src/`, server and build files. Read the GGML anchors to understand fallback and readiness, and obtain separate authority for any GGML changes. Treat graph/model, sampling, and loader anchors as read-only references.

The earlier `observability.expert_route_capture` 1.0.1 probe supplies a reference for post-selection reads and independent greedy-ID parity. Its Granite count applies to its fixed decode campaign. Use the Fill receipt for existing phase and observer placement when revising a Fill-style tree. Reuse wait-analysis fixtures if they are available to the task. The recorder must gather its own prefill, transfer, and readiness evidence.

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

## Granite projected route provenance

At stock pin `9048bad8d6e3a0f9f1726e238e451181c7e02613`, `src/models/granite.cpp` gathers output rows before the final FFN and `src/llama-graph.cpp` fills the `out_ids` mapping from the stock microbatch. The authoritative Granite runtime evidence reproduces the final-layer prefill loss. [PROJECTED-ROWS.md](PROJECTED-ROWS.md) describes the handling while preserving stock routing and output.
