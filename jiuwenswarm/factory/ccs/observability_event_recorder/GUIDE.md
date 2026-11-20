# Runtime Event Recorder Builder

Build the **Runtime event recording** subcomponent of **Generation runtime** in the task-owned llama.cpp checkout at `9048bad8d6e3a0f9f1726e238e451181c7e02613`. Record selected MoE experts and scheduler observations while preserving inference behavior. Read the work order, [component specification](components/runtime_event_recorder/component.yaml), [ontology slice](ONTOLOGY.yaml), and [source map](SOURCE-MAP.md) before editing the owned engine source.

## Zero footprint when off

When `LLAMA_EVENT_REC` is unset, use the stock path after one cached `getenv`
check. Do zero component work beyond that check. Emit zero lines with the
`runtime_event_recorder:` prefix, including at teardown. The `active`,
`inactive (<reason>)` and `stats` markers are emitted only when the gate
is set. Keep the cached presence bit distinct from eligibility so a set but
invalid value can still report a reason.

```cpp
void example_first_use() {
    static const char * const gate = std::getenv("LLAMA_EVENT_REC");
    if (gate == nullptr) return;
    LLAMA_LOG_INFO("runtime_event_recorder: inactive (example only)\n");
}
```

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

## 1. Establish the contract and baseline

Resolve the task's source, contract, constraints, run configuration and resource grants. Verify the base pin with `git rev-parse HEAD`, or verify the base of an existing integration with Git ancestry. Identify the model's routed layers, the authoritative request and phase metadata, the workload, how to compare greedy output, and the capacity and time budgets. Freeze the baseline and workload before changing the engine. The task template uses `star-prefill-v0` as its contract placeholder.

Apply these defaults where the contract is silent and record each choice and its reason as `chosen_by_cc`.

| Decision | Default and reason |
| --- | --- |
| First supported workload | One tagged server request with prefill and greedy decode, without speculation and with the native MoE cache disabled. This gives authoritative caller tags and isolates the stock copy path. |
| Join identity | Assign a monotonic dispatch ID across the output stream. Carry the server task ID and `is_prompt` through the stock batch row map. A reused graph or a one-token prefill can otherwise be mislabeled. If mixed rows are in scope, carry request, phase and IDs per row in the same microbatch-layer event. |
| Clock and transfer units | Use `std::chrono::steady_clock` in nanoseconds and count actual submitted expert-weight bytes, including scheduler padding. A proven resident path contributes zero. An unobserved path is incomplete. |
| Capacity and lifetime | Default to 64 MiB, overridden by a positive whole decimal `LLAMA_EVENT_REC_MIB`. Reserve against the shared ledger before allocation and charge ring, join, staging and serialization storage. Use the smaller of the configured cap and authorized reservation. Keep retained order by dropping newest rather than blocking dispatch. |
| Output | Drain at normal exit into a fresh task-owned JSONL path. Use one event per complete microbatch-layer and a final summary with coverage, loss and recorder timing. Verify exclusive creation at the cold write boundary. |
| Acceptance | Require full coverage and zero loss in the normal run. Force accounted drops separately. Use a 3% end-to-end overhead bound where the contract is silent, following the factory observability precedent. |

## 2. Find the hooks and choose how to integrate

Use the pin and symbols in [SOURCE-MAP.md](SOURCE-MAP.md). Start with the server's dispatch, then follow `process_ubatch` and the existing eval and copy callbacks. Search the owned checkout for `LLAMA_EVENT_REC`, the top-k tensor name and existing capture or Fill observers. If a recorder exists, trace its gate, ownership, hooks and writer, then revise them in place. If absent, design the state and writer under `src/` and register any new source in the library build. Use the three samples to reason about gate lifetime, marker format and bounded drain behavior. Write the integration in the task checkout.

1. Gate setup before enabling hooks. An unset variable must take the stock path after one cached environment lookup, without recorder allocations, logs or file access. Treat an empty path, invalid capacity or failed reservation as an enabled error. Choose where to validate the path outside dispatch. Handle races at exclusive creation and never overwrite earlier evidence.
2. Attach identity where the server still knows row ownership and phase. Remap by the actual ubatch row indices. Preserve the caller's eval callback ask/read/stop behavior on both graph creation and reuse. Match `ffn_moe_topk-<layer>` exactly and read completed I32 IDs with the tensor's actual dimensions and strides. Observe before any cache-slot remapping. Preserve the order of IDs and leave the mixture weights untouched.
3. Attribute bytes at the submission that actually runs in `sched_copy_experts`. Check fallbacks in the scheduler and cache-handled branches before declaring coverage. Use the dispatched graph's first expert consumer and its required dependencies to choose a host observation boundary for readiness. The eval callback's ask is pre-compute but does not establish dependency completion. Its read is synchronized after the requested node. Prefer an existing supported boundary when it supplies the timing the contract needs, and describe what the timestamp measures. If an exact pre-submit boundary or fallback accounting needs a GGML edit, obtain work-order authority first. Choose a supported workload or record the unmet signal when the existing hooks cannot observe it.
4. Complete the join on successful eligible dispatch. Keep duplicate, failed and incomplete observations distinct so that each expected row is accounted for once. Count dropped or unwritten eligible rows in disjoint loss buckets. Quiesce producers before one final drain, save observed loss even if JSONL writing fails, and preserve the stock path on recorder failure. Keep allocation growth, file I/O and logging out of per-event processing.

## 3. Check activation before accepting parity

- Use `-lv 4` to see the library's INFO lines. Require one `runtime_event_recorder: active` first-use line and one stats line at normal exit in the successful enabled arm. Matching output with the gate set does not prove the recorder ran. In an error arm require `runtime_event_recorder: inactive (<reason>)` and the exit stats line.
- On this Jetson, `-lm auto` can resolve to `none` for the tested device configuration. With `-lv 4`, check for `load_tensors: ... (load_mode = none)`. Select `-lm mmap` when an observed path depends on mapped weights, and confirm `(load_mode = mmap)` in the log. Keep the effective load mode consistent across parity arms.
- Compare within one frozen configuration. Even stock can produce different tokens under `-ngl 0` and `-ngl 99 -cmoe`. Hold model, load mode, offload, cache, prompt, seed, sampling and token limits fixed across stock, recorder off and recorder on.
- A worker sandbox cannot use the GPU or open ports. Use it for fixtures, static `verify`, standalone syntax, and analysis of existing captures. Run live server activation, parity, runtime JSONL coverage and overflow, graceful-exit flush, and hardware overhead in an authorized real shell. Use [helper usage](helpers/README.md) for captured evidence.

## Done criteria

Retain the proposed diff, native verdict, and full compile/link evidence for every touched translation unit and dependent of a changed header. Require observed activation, fallback, same-configuration greedy parity, complete prefill and decode coverage, accounted overflow and measured overhead under the contract. Follow [METHOD.md](METHOD.md) and [VALIDATION.md](VALIDATION.md). The native `done` flag covers the static checklist. The pilot template limits its claim to its requested activation and parity smoke evidence.
