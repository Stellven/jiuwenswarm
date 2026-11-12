# Expert streaming into an existing llama.cpp

On UMA with mmap, selected experts' weight pages are read from the GGUF mapping
on demand. In stock llama.cpp the compute thread takes the page faults. This
capability targets MoE with CPU-side experts (`-cmoe`/`--cpu-moe` or CPU `-ot`
overrides), expert bytes much greater than available memory, and mmap loading.
Use applicability first: it reads only the model header and host memory. Its
2x memory heuristic is guidance, not a performance prediction; partial placement
and unknown mappings need inspection. Read SOURCE-MAP.md for source anchors.

This is not expert placement: CPU vs GPU residency, `--n-cpu-moe`, and `-ot`
are placement controls. No component here moves experts to the GPU.

## Choose a mechanism

- Demand-driven fill (`expert_fill`) reads selected nonresident ranges through
  parallel buffered reads before computation. Try this first when decode faults
  suggest demand IO; it has a direct engagement and decode-byte test.
- Predictive reads (`expert_pregate`) try upcoming expert routes and schedule
  asynchronous reads. Try only after understanding fill-only evidence; routing
  recall cannot establish that data arrived early enough.
- Supporting integration/observability: `mmap_advice` and `router_prefetch` are
  source prerequisites for fill. diag/observe explain faults and scheduling;
  `thread_names` (patch 09) names fill workers xfill-N so the lab's thread
  sampler can attribute them; it must be integrated before it can engage.
  `expert_readiness` (patch 10) measures, at each layer arrival and before demand
  fill, which selected bytes were already resident, split by predicted vs not,
  plus wasted speculative bytes and demand bytes that duplicated an in-flight
  read. `inflight_join` (patch 11, performance) removes those duplicate reads by
  waiting on the in-flight async read; its source needs patch 10, but readiness
  can stay switched off at run time.
  `phase_stats` (patch 16, observability) prints decode-only fault, context
  switch and CPU-time deltas plus per-token latency p50/p95/max, with fill on
  or off, so cost can be attributed without a perturbing trace.

Source dependency does not mean runtime enablement. A present patch's switch
stays off unless its own evidence supports it. Keep failed prerequisites dormant
only under AB.md step 9, recording needed_by and the off settings in every arm.

## Decide from evidence

Read EVIDENCE.md and factory.methodology_ab before integrating. Start with the
identified working engine and frozen reference; inspect effective configuration,
source dependencies, engagement, and load/prompt/decode separately. Fill not
engaged means check effective configuration before changing the mechanism.
High recall with low readiness suggests reads arrive too late (timing, queue
depth or device bandwidth) rather than wrong guesses; test which before acting.
Fewer faults with unchanged decode time means IO may not be the bottleneck;
inspect compute and critical-path waits before adding more IO. Whole-run IO or
copy time alone cannot locate decode cost. Missing readiness, per-phase faults,
critical-path matmul stalls or page-cache pressure limit attribution (see source
map). Stop or change direction when a bounded trial contradicts its hypothesis,
no discriminating measurement is available, or the budget/stop condition is met.
A failed or null idea is retained knowledge.

## Bounded settings trials

At most 3 settings trials per component. Publish a justified, falsifiable
hypothesis for each, vary one knob per trial, keep the workload fixed, and use
env-only untraced ABBA on an admitted image. Engine strict validation owns value
range checking: an abort is evidence. These are the component env_ranges (source
revision qualifications matter):

- `LLAMA_EXPERT_FILL`: 0|1
- `LLAMA_EXPERT_FILL_CHUNK_KIB`: 03: 1..65536, otherwise fallback 1024; 08: strict 64..65536
- `LLAMA_EXPERT_FILL_DIAG`: 0|1
- `LLAMA_EXPERT_FILL_DIAG_CSV`: nonempty path; optional; only used with diagnostics
- `LLAMA_EXPERT_FILL_MAX_TOKENS`: 04: unsigned integer, 0 unlimited; 08: 0..2147483647
- `LLAMA_EXPERT_FILL_MIN_TOKENS`: 04: unsigned integer, 0 unlimited; 08: 0..2147483647
- `LLAMA_EXPERT_FILL_POPULATE`: 0|1
- `LLAMA_EXPERT_FILL_RANDOM`: 0|1|decode (decode added by 04)
- `LLAMA_EXPERT_FILL_THREADS`: 03: 1..256, otherwise fallback 8; 08: strict 1..64
- `LLAMA_EXPERT_PREFETCH`: 1 enables; otherwise off (08: strict 0|1)
- `LLAMA_EXPERT_PREFETCH_NEXT`: 1 enables next-layer same-ID prediction; otherwise off (08: strict 0|1)
- `LLAMA_EXPERT_PREGATE`: 0|1
- `LLAMA_EXPERT_PREGATE_K`: 1..32
- `LLAMA_EXPERT_PREGATE_LOOKAHEAD`: 1..2
- `LLAMA_EXPERT_PREGATE_MAX_INFLIGHT`: 1..64 (also capped by fill threads)
- `LLAMA_EXPERT_PREGATE_ORDER`: after|before
- `LLAMA_MMAP_ADVICE`: random enables; any other value keeps default advice
