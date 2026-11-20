# llama.cpp source map

Anchors below were checked in
`~/predemo/llama.cpp-stock`, HEAD
`9048bad8d6e3a0f9f1726e238e451181c7e02613`.

| Stock file and anchor | Access | Purpose |
| --- | --- | --- |
| `common/arg.cpp:229` `parse_tensor_buffer_overrides`; `:781` `common_params_parse_ex`; `:963` override padding; `:1377` `common_params_parser_init`; `:2729` `-ot` registration | Extend | Register the plan option, reuse stock buffer resolution and install staged overrides before null padding. |
| `common/common.h:476` `common_params`; `:555` its `tensor_buft_overrides` | Extend | Own plan state and ensure the strings behind override pointers outlive use. |
| `common/common.cpp:1238` `common_fit_apply`; `:1276` `common_init_result::common_init_result`; `:1686` `common_model_params_to_llama` | Extend | Check fit compatibility, retain stock parameters for retry, and pass overrides into the model load. |
| `src/llama-model-loader.cpp:1211` `llama_model_loader::create_tensor`; `:1330` override scan; `:1366` mmap host substitution | Read or extend readback only | First `std::regex_search` match wins, CPU can select an extra buffer and mmap can replace the requested host buffer. Inspect these branches without changing their selection behavior. |
| `src/llama-model.cpp:1708` `llama_model_base::load_tensors`; `:1720` load mode resolution; `:1747` effective mode INFO; `:2177` `load_all_data` call | Extend | Read actual committed tensor buffers after load, preserving stock allocation and mapping. |
| `src/llama.cpp:90` `llama_max_tensor_buft_overrides` | Read | At this pin the padded table has 4096 entries. |
| `ggml/include/ggml-backend.h:37` `ggml_backend_buft_name`; `:69` `ggml_backend_buffer_get_type` | Read | Get the effective buffer type name from a loaded tensor's buffer. |
| `ggml/include/gguf.h:84` `gguf_init_from_file`; `:131` `gguf_get_tensor_name`; `:134` `gguf_get_tensor_size` | Read | Compare inventory data against actual model metadata. |
| `common/log.h:124` `LOG_INF`; `src/llama-impl.h:28` `LLAMA_LOG_INFO` | Read | Use the stock INFO level for placement markers. |
| `src/CMakeLists.txt:37` `LLAMA_CORE_SOURCES` loader entry; `tests/CMakeLists.txt:98` `llama_build_and_test` | Extend | Register the new implementation and engine-side test. |

Candidate files can include `src/llama-placement-plan.{h,cpp}`, `src/llama-placement-plan-log.h`,
`tests/test-weight-placement-planner.cpp`, `scripts/placement_budget.py` and
`scripts/tests/test_placement_budget.py` when the corresponding parts are
absent. Reuse existing owners and entry points when present. The local Fill patch touches loader and model files. Preserve its
existing behavior when composing with it. The brief names
`engine.heterogeneous_placement_lab` and `placement_budget.py` as donors.
Neither was found in the supplied catalog or the local reference trees.

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
