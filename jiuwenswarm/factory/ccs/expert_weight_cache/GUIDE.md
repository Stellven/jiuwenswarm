# Expert weight cache

Build bounded reuse of staged expert weight slices in the owned llama.cpp checkout at
`9048bad8d6e3a0f9f1726e238e451181c7e02613`. The existing scheduler supplies the
selected experts and the stock copy establishes the byte ranges. The cache delivers
those bytes to the same destinations. It leaves token order, router IDs, mixture
weights, quantization and sampling to stock.

## Zero footprint when off

When `LLAMA_EXPERT_CACHE` is unset, use the stock path after one cached `getenv`
check. Do zero component work beyond that check. Emit zero lines with the
`expert_weight_cache:` prefix, including at teardown. The `active`,
`inactive (<reason>)` and `stats` markers are emitted only when the gate
is set. Keep the cached presence bit distinct from eligibility so a set but
invalid value can still report a reason.

```cpp
void example_first_use() {
    static const char * const gate = std::getenv("LLAMA_EXPERT_CACHE");
    if (gate == nullptr) return;
    LLAMA_LOG_INFO("expert_weight_cache: inactive (example only)\n");
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

## Inputs

Read the task's source pin, owned checkout, `component_cc`,
`constraints.engine_slice`, `contract_id`, `initial_run_config`, target, grants and
budget. From the contract use the fixed model and workload, greedy stdout baseline,
placement and load mode, and shared capacity ledger with the remaining bytes in the
target pool after weights, KV, compute buffers and headroom. Use the
`expert_weight_readiness` slice for selected-expert, weight-range, copy, readiness
and memory-budget evidence. Preserve explicit contract settings. Bind the
contract to the frozen stock reference before runtime acceptance.

## Defaults

| Field | chosen_by_cc | Reason |
| --- | --- | --- |
| Requested cap when `LLAMA_EXPERT_CACHE_MIB` is unset | 64 MiB | Bounds an opt-in experiment without reserving a large part of shared memory. |
| Effective cap | Minimum of the requested cap and ledger-admitted bytes in the destination pool | Gives model, KV, compute and concurrent reservations their budget. Missing or exhausted admission means zero cache bytes and a logged stock fallback. |
| Cap parsing | Whole decimal MiB; zero disables admission and invalid or overflowing values take the stock path | Makes the accounting unambiguous. |
| Ownership and key | One cache per context and model lifetime; one expert lease per graph-compute operation, keyed by model generation, layer, expert and destination backend; the lease groups exact tensor ranges and representation | Shares the lease when several tensors of one expert are read and prevents reuse across incompatible data. |
| Replacement and admission | Demand-only; least recently used unleased entry first; oversize or pinned-full demand uses a plain copy | Gives bounded reuse with deterministic replay and keeps live readers safe. |
| Reader completion | Release at the existing context scheduler synchronization boundary after all readers finish, including partial submissions and teardown | Gives a conservative completion guarantee without a new scheduler event path or a per-hit fence. |
| Backend eligibility | Use a persistent staged allocation on the destination backend and only reuse on an established same-backend copy path that avoids a host upload; use the stock path if the backend or mapping provenance is unsupported | Avoids treating a recycled scheduler tensor, a host bounce or a resident mmap page as a transfer saved. |
| Logging and counters | Prefix `expert_weight_cache`; report effective cap and backend on activation, plus `leases`, `reuses`, `evictions`, `bytes_copied_saved` and `peak_bytes` at teardown | Exposes eligibility, transfer accounting and the cap in one context-lifetime record. |

The feature gate is the brief's `LLAMA_EXPERT_CACHE=1`. An unset value or any
value other than the literal `1` leaves the feature off. Explicit `-lm mmap`
is required for mapped weights. Confirm the tensor byte range belongs to a live
model mapping, using the loader's actual effective mode and backing range.

## Build or revise

1. Confirm the checkout pin and inspect its current diff. Use [SOURCE-MAP.md](SOURCE-MAP.md)
   to trace the scheduler's host-weight callback to the selected IDs, exact
   offsets and trailing padding. Identify how the owned tree exposes the
   effective loader mode, mapping bounds and destination copy support.
2. Inspect the owned tree and its diff from the pin for an existing cache, lease,
   or Fill-style range provider. If a staged cache already exists, revise its
   gate, accounting, identity and lifetime in place. Preserve unrelated Fill
   behavior and reuse its range/ownership information if it can prove the same
   backing bytes. Stock native MoE cache remains independent. If configured
   (`cparams.moe_cache_size > 0`), emit the capsule's inactive line and leave the
   entire native copy path in charge, including its own fallbacks.
   Keep router, sampler and model files read-only. For stock, identify existing
   host buffer provenance before designing the cache. A host-buffer flag alone
   does not prove a range is mapped. On Satay a context-side provenance adapter
   can inspect file-backed mappings at setup and match device, inode and offsets
   to the loaded GGUF and its tensor ranges where that identity is available.
   Reuse trusted mapping metadata if an existing Fill integration exposes it.
   Treat unknown identity, bounds or mapping lifetime as ineligible.
3. Put the cache state and range/lease logic in the dedicated `src/llama-expert-weight-cache.*`
   files for a fresh integration. Hook `llama_context::graph_compute` for
   operation ownership, `sched_copy_experts` for authoritative demand, and
   `synchronize`/teardown for retiring outstanding readers. If no eligible copy
   hook is reached, an enabled invocation must still report its inactive reason
   by context teardown. Keep the off path on stock, without cache allocation or
   a new synchronization. The stock `copy_experts.reset()` resets selection
   bookkeeping before graph submission. Do not use it to retire leases from
   earlier operations that may still have pending readers.
4. Validate source range, destination representation, backend and lease before
   suppressing any stock transfer. Stage immutable bytes in a separate,
   ledger-charged allocation with a stable lifetime. Retain that allocation via
   the operation's shared lease until the last reader completes. A hit uses the
   staged bytes to fill the stock destination. Prove reuse within one operation
   first. Any reuse across operations needs the same verified source identity,
   representation and readiness. Preserve selected-expert offsets,
   handling of consecutive ranges, and stock trailing padding, including where a
   cached range meets an uncached one. If a range or its padding cannot be proven
   identical, use the original plain copy. Hold any partially submitted lease
   through completion even if the rest of the operation falls back.
5. Reserve and release the actual allocation sizes including alignment, cache
   metadata and temporary copies. Include bytes held by outstanding leases in
   ledger usage and `peak_bytes`. Coordinate reservations across contexts
   sharing a pool, since each context has its own cache. Publish a reusable
   entry only after staging has completed or its readiness can be ordered before consumption. Inspect
   the pinned backend copy implementation, because a generic async copy can
   fall back to host staging or introduce synchronization. On lease,
   allocation or staging error, stop serving cache hits for that context, log an
   inactive reason once on that transition, and use the plain copy path.
6. With the gate set, emit one INFO decision at first use
   (`expert_weight_cache: active cap_mib=… backend=…` or
   `expert_weight_cache: inactive (…)`) and one INFO stats line at context
   teardown. A late failure after activation may emit one additional inactive
   transition. Count leases once per operation/expert. Count a reuse once for
   each lease that consumes already-staged bytes. Count only completed replacement evictions.
   `bytes_copied_saved` counts stock source-to-destination upload bytes avoided
   by hits, excluding padding still uploaded and any host bounce. Retain
   separate traffic measurements for staging and backend copies.

## Runtime pitfalls

- Library INFO lines appear at `-lv 4`. Capture stderr at that verbosity and
  require the cache's `expert_weight_cache: active` line from the same run.
  Matching output with the gate set can be a stock fallback.
- On this Jetson, `-lm auto` resolves to `load_mode = none`. Check stderr for
  `load_tensors: ... (load_mode = none)` and rerun the positive case with
  `-lm mmap`. Confirm `load_mode = mmap` before judging engagement.
- Compare outputs within one configuration. Even stock can produce different
  tokens with `-ngl 0` and `-ngl 99 -cmoe`. Freeze model, prompt, seed, request
  length, placement and load mode across each baseline and candidate comparison.
- Worker sandboxes cannot use the GPU or open ports. Run static verification,
  sample syntax checks and offline fixture or log analysis there. Use an
  authorized real shell on Satay for configured CUDA builds, server-mediated
  activation and parity on port 5175, native-cache and non-mmap bypass runs,
  and any hardware measurement.

[Samples](samples/) illustrate the gate, INFO lines, lease ownership and cap
arithmetic. [Helpers](helpers/README.md) cover log checks and one-shot parity.

## Done

Keep the candidate diff and the ordered checks in [METHOD.md](METHOD.md).
The native `verify` result covers static checks. Builder completion also requires
a configured compile of every touched translation unit, runtime marker evidence
including bypass, exact greedy stdout parity, and a replay of lease lifetime and
error paths. Positive reuse on a repeat-demand workload and the transfer counters
establish engagement. A throughput or speed claim requires measurements on the
target hardware under the same frozen workload. If an obligation cannot be
checked, report the evidence available and leave builder completion open.
