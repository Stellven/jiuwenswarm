# Weight placement planner

Build an offline byte-budget planner and the pinned llama.cpp loader's plan
readback. The builder owns the candidate diff. Start with the work order,
immutable contract, [component spec](components/weight_placement_planner/component.yaml),
[ontology slice](ONTOLOGY.yaml), and [source map](SOURCE-MAP.md).

## Zero footprint when off

When `LLAMA_PLACEMENT_PLAN` is unset, use the stock path after one cached `getenv`
check. Do zero component work beyond that check. Emit zero lines with the
`weight_placement_planner:` prefix, including at teardown. The `active`,
`inactive (<reason>)` and `stats` markers are emitted only when the gate
is set. Keep the cached presence bit distinct from eligibility so a set but
invalid value can still report a reason.

```cpp
void example_first_use() {
    static const char * const gate = std::getenv("LLAMA_PLACEMENT_PLAN");
    if (gate == nullptr) return;
    LLAMA_LOG_INFO("weight_placement_planner: inactive (example only)\n");
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

## Build in this order

1. Verify the owned checkout's pin against the source map. Search for
   `placement-plan`, `tensor_buft_overrides`, `create_tensor`, and the
   post-load buffer queries. Inspect the owned delta for existing planner,
   option, and logging code. If present, extend the same entry points and state
   owner in place, preserving compatible behavior and tests. If absent,
   register the option beside `-ot` and isolate new engine code under `src/`.
   Keep stock routing, sampling, quantization and allocation policy intact.
2. Assemble inventory from GGUF tensor names and byte sizes, binding the
   model digest, quantization and effective launch settings. Identify backing
   storage, ranges, proven aliases, buffer candidates, charges and lifetimes.
   Include phases for loading, prefill and decode, and add boundaries at every
   acquisition and last reader. Import the host cap and phase-specific KV,
   compute, headroom and committed bytes from the shared capacity ledger.
3. Calculate stock per-phase charges first. Charge the union of live shared
   ranges per backing identity, count replicas and padding separately, and
   count both sides of transfers while live. For each candidate, subtract
   charges safely from the cap or use checked addition. Use the worst phase
   to admit the plan. Check that displacement releases physical backing only
   after its last reader. Keep one logical assignment per tensor. Retain an
   inventory-complete ledger with stock rows, rejected moves and phase totals.
4. Emit the strict version 1 engine JSON described by the component. Keep
   cap, peak, inventory and load settings in the bound admission record,
   outside the engine wire JSON. Define how the load obtains those values
   from the trusted run inputs and ties them to the chosen plan. If the
   binding is unavailable, report inactive instead of inventing cap or peak.
   For generated plans, emit regex-escaped, anchored exact names. For
   supplied plans, validate patterns with stock C++ regex semantics. Check
   the resolved tensor matches against the inventory, reject overlapping
   assignment rules and unresolved buffers, and preserve stock for unmatched
   names. Use the structural helper before exercising the engine parser.
5. Parse the CLI option and its environment alias while respecting stock
   parser precedence. Read the gate once per process and stage the entire
   override table before the model load. Bound input before parsing. Reject
   duplicate keys, validate the shallow schema before allocating overrides,
   and keep strings alive through the loader's last
   use of their pointers. Leave room for a null sentinel after all plan and
   stock entries. Check existing `-ot` and `-cmoe` patterns for overlap.
   Keep the original parameters available for atomic fallback.
6. Read committed buffers after load, including CPU extra buffers and mmap
   substitutions. Reconcile per-name planned and actual buffer types and
   bytes before emitting active. On a plan-specific failure discard the staged
   state. If a plan-specific load has started, release the candidate before
   retrying with stock parameters. Emit the inactive reason once and one stats
   line at orderly exit. Count assignments from the committed model and
   keep stock logging unchanged when the gate is unset.

## Defaults and reasons

Record each applicable choice as `chosen_by_cc` with its reason when the work
order is silent.

| Default | Reason |
| --- | --- |
| Exact env value `1` and explicit plan file | Opt-in is unambiguous. Any other set value or a missing file gets an inactive reason. |
| Literal names for generated plans, strict 4 MiB input and a 16 MiB cap on engine-owned plan state | Exact names make reconciliation reproducible. Account for parser and installed state concurrently and free transient state after staging. |
| At most 4095 entries across stock and plan overrides | The pinned 4096-slot table needs a null sentinel. Reject excess before installing. |
| Whole-run lifetime for unspecified backing, with load accounted separately | Unspecified lifetimes give no basis for reuse. Loading can overlap sources and destinations. |
| Full distinct backing charge until physical sharing is established | Equal names or sizes give no evidence of aliasing. Charge all required copies. |
| Higher declared priority first, lexical tensor name on ties | Deterministic admission. Displacement requires evidence of final release. |
| Keep stock when no candidate is evidenced. Return a stock-only unresolved record if cap or reservations are unknown, or an infeasible record if stock exceeds a known cap | Stock is the fallback. Missing capacity cannot establish admission. |
| Fixed flags, `-fit off`, explicit `-lm mmap` for mapped plans, and inactive on a stock override conflict | Reproducible settings preserve the intended stock control and avoid accidental first-match precedence changes. |
| Class summaries plus exact-name readback | Totals can hide assignment swaps. Use actual committed buffer names and bytes to reconcile. |

## Pitfalls on Satay

- Library INFO markers require `-lv 4` in these runs. Capture the full server
  log through orderly exit so the stats line is visible.
- Jetson `-lm auto` resolves to no mmap for the offload configuration. Look
  for `load_tensors: ... (load_mode = none)` in the log. Mmap-dependent paths
  can remain silently inactive. Request `-lm mmap` on both sides when a mapped
  plan is intended and confirm the resolved mode.
- Stock `-ot` uses first-match regex search. Host-buffer replacement and
  CPU extra buffers can make the allocated buffer differ from the requested
  buffer. Read back the actual allocation and check it against the expected
  effective assignment.
- Matching output with the gate set proves parity only. Require the
  `weight_placement_planner: active` line for engagement as well as the
  matching assignment readback and exit stats.
- Compare within one configuration, including model, prompt, seed, KV,
  offload, fit and load flags. `-ngl 0` and `-ngl 99 -cmoe` produce
  different tokens even on stock. For the active control reproduce the same
  effective placement on stock with `-ot`.
- A worker sandbox cannot use the GPU or open ports. It can inspect the pin,
  run fixture and helper tests, and invoke static verify. Real server parity,
  GPU activation, real readback and residency/timing measurements need an
  authorized real shell. Engine builds and process control are outside this
  revision worker's authorization.

## Done

Follow [METHOD.md](METHOD.md) in order. Retain the source identity, authored
diff, static receipt, compile evidence for every touched unit, admitted plan
and ledger, exact assignment readback, fallback logs, and both byte-identical
greedy controls. Record the highest stage supported by the evidence.
