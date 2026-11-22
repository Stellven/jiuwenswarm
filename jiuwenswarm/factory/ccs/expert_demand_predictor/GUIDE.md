# Expert demand predictor

Build an optional read-ahead hint producer for the next MoE layer during single-slot prefill. Learn from the router's completed selections. The router remains authoritative, and stock demand proceeds without waiting for speculative work. The builder authors the source diff in its task-owned checkout.

## Zero footprint when off

When `LLAMA_EXPERT_PREDICT` is unset, use the stock path after one cached `getenv`
check. Do zero component work beyond that check. Emit zero lines with the
`expert_demand_predictor:` prefix, including at teardown. The `active`,
`inactive (<reason>)` and `stats` markers are emitted only when the gate
is set. Keep the cached presence bit distinct from eligibility so a set but
invalid value can still report a reason.

```cpp
void example_first_use() {
    static const char * const gate = std::getenv("LLAMA_EXPERT_PREDICT");
    if (gate == nullptr) return;
    LLAMA_LOG_INFO("expert_demand_predictor: inactive (example only)\n");
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

## 1. Establish the baseline and choose settings

Read the task's source pin, contract, engine slice, resource grants and budget. Confirm the owned checkout starts at `9048bad8d6e3a0f9f1726e238e451181c7e02613` and inspect the pinned anchors in [SOURCE-MAP.md](SOURCE-MAP.md). Record the frozen baseline, model, prompts, phase and slot settings, trace identity and memory ledger. If baseline or trace evidence is missing, continue the source work and report the corresponding acceptance check as pending.

Use the [component specification](components/expert_demand_prediction/component.yaml) for work-order requirements. Record defaults for unspecified details as `chosen_by_cc` with their reasons.

| Decision | Default and reason |
| --- | --- |
| History and cold start | Treat each observation as a set of actual IDs. For target layer L+1, use the current microbatch's completed layer L and the previous two completed microbatches' observations at L+1 in this request. Use available sets during cold start and reset between requests. This avoids future-data leakage and repeated-token skew. |
| Confidence and lead | Divide each winning ID's count by the number of contributing sets. Express intended lead as one layer and record observed lead using a monotonic clock at submission and matched consumption. This makes sparse history and actual timing distinguishable. |
| Advice and accounting | On Linux use a status-returning WILLNEED advice call (for example, `madvise` with `MADV_WILLNEED`). Charge unique page-rounded ranges before advice. Keep each charge until usefulness is supported or the request ends. This bounds speculative reads when actual page residency cannot be established. |
| Replay split | Freeze the rule before replaying the last 20% of complete requests in chronological order, rounding up and leaving at least one earlier request. Request boundaries prevent training and holdout leakage. |

## 2. Locate and integrate the observation

- Search the owned checkout for Pregate, Fill, predictor and existing evaluation callbacks. If a predictor exists, update its state and hooks in place. Remove superseded prediction paths, preserving unrelated Fill, native cache and demand copies. If absent, prefer a new private unit under `src/`, registered in the stock CMake list, with state owned by the context.
- Follow request metadata into decode and through microbatch splitting. One unique sequence in a microbatch establishes neither the server's slot mode nor the prefill phase. Use an authoritative phase/slot boundary and preserve its identity through graph reuse. Bypass when identity or completion is ambiguous. Skip the final layer where no target exists.
- Trace `ffn_moe_topk-<layer>` from graph naming through scheduler completion. Chain the stock callback's ask and completion behavior and preserve its user data. An evaluation callback can add backend synchronization. Prefer an existing observation with equivalent completed IDs where it covers the admitted configuration. The copy callback can see IDs on the split host-weight path, but stock CPU and alternate placement may never enter it. Measure any synchronization introduced.
- Process one observation per request, microbatch and layer. Validate integer type, shape and stride before reading tensor contents. Use the scheduler backend for readback when the data is device-owned. Observe the target layer for scoring after its forecast has been made.

## 3. Resolve mapped ranges and account for their lifetime

- Resolve each predicted ID to the next layer's actual expert tensors, including fused gate/up or separate projections. Validate expert count, strides, byte extent, overflow, host backing and real mapping lifetime. For aliased tensors, charge the union of page-rounded ranges. An expert ID is useful for replay scoring even if a hint for it cannot be admitted.
- Bound all predictor-owned history, pending metadata and scratch to 1 MiB per context. Keep potential waste within 8 MiB per request and within ledger-admitted shared capacity. Skip work whose range or cost cannot be proven. Stop hint work before teardown invalidates context or mappings.
- Preserve the demand path and scheduler return values. A terminal advice failure disables further hints and records one inactive transition. The gate is default off and only exact `1` requests activation. At INFO, log the first effective outcome and requested-run exit stats. Activate only after confirming an eligible phase, observation and mapped hint path.

## 4. Score and verify

Count hits as distinct actual IDs present in the forecast and misses as distinct actual IDs absent from it. Report coverage as hits divided by hits plus misses and leave it unavailable for an empty denominator. Count useful bytes only with evidence of hint-attributable readiness at consumption. Advice success establishes submission. Keep bytes without demonstrated usefulness charged conservatively, and report lead sample count alongside total lead.

- Library INFO lines appear at `-lv 4`. Check the server log at this level, including exit stats after orderly shutdown. Matching greedy output with the gate set is parity evidence. Engagement requires `expert_demand_predictor: active` on the eligible run.
- On this Jetson, `-lm auto` resolves to `load_mode = none` and mapped hints cannot run. Check for `load_tensors: ... (load_mode = none)` in the server log. Specify `-lm mmap` for the activation test and confirm the effective mode and the backing of the selected ranges.
- Compare only within one configuration. Stock `-ngl 0` and stock `-ngl 99 -cmoe` can produce different tokens. Hold model, prompt, seed, batch settings, load mode and placement fixed across each stock, candidate-off and candidate-on comparison.
- A worker sandbox cannot open ports or use the GPU. It can run static verification, sample checks, synthetic replay and offline log comparisons. Server activation, GPU parity and hardware measurements require an authorized real shell. The Satay revision worker also leaves target engine builds to the builder.

The completed change has an authored diff, a retained native verdict, a successful target build, eligible activation and fallback logs, matching greedy output and routing, bounded memory and wasted reads, and held-out trace results. Apply additional contract thresholds and use the stage labels in [METHOD.md](METHOD.md). The [samples and helpers](helpers/README.md) support individual checks.
