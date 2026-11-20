# Predictive prefetch on the stock native expert bank

1. Read all imported Factory reports and their exact identities. Record a real
   plan decision before edits with `action.summary`, evidence IDs, candidate
   hypotheses, planned control flags and stop conditions. Confirm the legacy
   predictor refuses `ctx->moe_cache != nullptr` and uses Linux host advice.
   Forecast accuracy or advice lead alone does not establish native readiness.
2. Keep routing, selected IDs, sampler, expert and slot capacity, stock load
   flags, and the ordinary demand lookup/refill/eviction path. `LLAMA_EXPERT_PREDICT`
   unset must preserve exact stock behavior and silence. Start with default
   A+ `--moe-cache-mib 30720 --moe-cache-cpu-share 0 -lm mmap --cpu-moe`, including
   stock context, batching and slot settings. Derive request or graph ownership
   from actual admitted decode/prefill metadata. Unsupported mixed or ownership
   cases bypass explicitly. A blanket one-slot restriction would leave the
   default A+ comparison ineligible.
3. Use the existing native bank, ownership and scheduler/backend stream ordering.
   Let its observed demand generate a bounded candidate set with stable keys
   for request or graph, layer, expert, device and slot generation. Skip existing
   residents, duplicates, in-flight demand, unavailable or pinned slots, and
   unsafe backend/graph cases. Demand keeps its priority. Do not change capacity,
   add a device bank, or expose a speculative slot to demand before verified
   completion. Issue only a provable missing copy with all required projections
   and exact quantized strides. A late prediction must use the ordinary demand
   fallback without stale slot reuse or numerical change. A measured inactive
   result is acceptable when the safe prerequisites cannot be met.
4. Keep bounded speculative admission and bytes per request and bound outstanding
   work. Synchronize or invalidate safely on cancellation, graph changes,
   overwrite and shutdown. Keep speculative completion, useful consumption and
   natural stock residency distinct. Gate-on operation must retain an actual
   marker plus a bounded terminal log. For each verified request or phase emit
   counters in `expert_demand_predictor: native phase=...` for `requested`,
   `already_resident`, `issued`, `issued_bytes`, `useful_ready`, `useful_bytes`,
   `miss`, `late`, `unused`, and `pending`. Report denied, duplicate or unknown
   outcomes separately if present. Tie late/unused classifications to real
   transfer and consumer lifetimes. Measure useful bytes at actual demand, not
   at submission or on a coincidental stock hit.
5. Add bounded verification of default-off behavior, prefetch miss admission,
   already-resident/duplicate skip, pending and late fallback, unused eviction,
   same-byte consumption, and cancellation/reuse. Verify the complete scoped
   stock diff with the native CC in the owned checkout and commit only this
   work. Preserve failures and unsupported coverage. Configured build and model
   jobs belong to the coordinator's later windows.
6. Functional evidence needs stock A+30, candidate gate off, and candidate gate
   on at equal requested and actual native bank allocations and exact default
   settings. Require matched greedy output and reasoning. Compare observed
   target counters against ordinary stock demand, and retain startup and actual
   copy bytes. Quiet mirrored timing belongs to the separate benchmark. Reports
   must distinguish the old host-advice C4 fixture from native-bank prefetch.
