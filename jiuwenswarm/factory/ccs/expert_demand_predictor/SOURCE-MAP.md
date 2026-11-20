# llama.cpp source map

Anchors checked in the clean stock checkout at `9048bad8d6e3a0f9f1726e238e451181c7e02613`.

| Stock path and anchor | Use |
| --- | --- |
| `src/llama-context.cpp:1817` and `:1847`, `llama_context::process_ubatch` | Attach the optional evaluation wrapper and track graph reuse. Keep the existing callback and its user data. |
| `src/llama-context.cpp:2140` and `:2367`, `llama_context::decode(const llama_batch_ext &)` | Establish the input and microbatch boundaries. Integrate prefill and slot eligibility using the contract's request metadata. |
| `src/llama-context.cpp:3128`, `llama_context::graph_compute` | Track the active graph identity. Stock resets the copy state before each scheduling call. |
| `src/llama-context.cpp:3159`, `llama_context::sched_copy_experts` | Demand-side reference. Native cache can consume the copy first. Otherwise stock derives the selected IDs and copies the matching host ranges. |
| `src/llama-context.cpp:633`, `llama_context::~llama_context` | Finalize predictor state and exit stats before destroying its dependencies. |
| `src/llama-context.cpp:3243`, `llama_context::graph_get_cb` | Stock formats graph-node names as base name plus layer suffix. Read as a naming reference. |
| `src/llama-context.h:157` and `:317`, `process_ubatch` and `sched_copy_experts` declarations | Store context-owned state and declare hooks without adding a public API. |
| `src/llama-batch.h:17` and `:44`, `llama_ubatch` and `n_seqs_unq` | Read batch identity and check unique sequences. Get phase from the real request lifecycle. |
| `src/llama-graph.cpp:2252` and `:2375`, `llm_graph_context::build_moe_ffn` | Stock constructs the authoritative expert IDs and emits the `ffn_moe_topk` node name. Read only. |
| `ggml/include/ggml-backend.h:96`, `:333` and `:388`, `ggml_backend_tensor_get`, `ggml_backend_sched_eval_callback` and `ggml_backend_sched_set_eval_callback` | Use existing readback and ask/completion callback interfaces. Read only. |
| `ggml/src/ggml-backend.cpp:2100` and `:2134`, `ggml_backend_sched_copy_input` | Checks host-weight eligibility before dispatching the copy callback. Read only. |
| `ggml/src/ggml-backend.cpp:2213` and `:2252`, `ggml_backend_sched_compute_splits` | Verify callback completion and synchronization behavior. Read only. |
| `src/llama-model.h:353` and `:949`, expert projection tensors and `llama_model::layers` | Resolve expert tensors for the next layer, including fused gate/up where present. |
| `src/llama-model.cpp:1708`, `:2082` and `:2184`, `llama_model_base::load_tensors` | Inspect ownership of mapped model buffers and retained mapping objects. Read only. |
| `src/llama-mmap.h:56` and `:57`, `llama_mmap::size` and `addr` | Validate real mapping bounds. Read only. |
| `src/llama-mmap.cpp:1067` and `:1133`, `llama_prefetch` | Reference for rounded mapped ranges and advisory read-ahead. The stock helper returns void. Read only. |
| `src/llama-moe-cache.cpp:965` and `:969`, `llama_moe_cache::copy` and `copy_experts` | Read the existing stock demand-cache interface. Preserve the native demand-cache behavior. |
| `tools/server/server-context.cpp:3952` and `:4465`, prompt processing and completion transitions | Locate server request phase and trace it into decode. Inspect mixed batches and the final prompt chunk before choosing a handoff. |
| `src/llama-model.cpp:1720` and `:1747`, effective load mode | Check the AUTO downgrade and the library INFO line reporting effective mode. |
| `common/arg.cpp:2666`, `-lm` parser | Use the explicit mmap mode for mapped read-ahead. Read only. |
| `src/llama-impl.h:28`, `LLAMA_LOG_INFO` | Emit INFO activation, fallback and stats messages. Read only. |
| `src/CMakeLists.txt:17` and `:70`, llama source list and C++17 target feature | Register the new implementation under the stock C++ standard. |

New files have no stock anchors. `src/llama-expert-fill.h` is an optional in-place update in a Fill checkout. Reference material read locally includes the Expert Pregate patches under `expert_streaming`, `~/predemo/receipts/fill-applied.diff`, and `engine.expert_cache_lab` in the prefill catalog for causal replay conventions. No standalone `factory.expert_prediction` package was located in those references.

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
