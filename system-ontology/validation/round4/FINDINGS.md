# Node types draft 0.4: independent checks, round4

44 types, 486 choices. Thresholds were fixed on 2026-11-16 in `validation/criteria.yaml`, before this draft was written.

| Check | Result | Threshold | |
|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 237/240 = 99% | at least 90% | pass |
| Decisions plainly covered by a choice | 635/715 = 89% | at least 80% | pass |
| Decisions covered only loosely | 70/715 = 10% |  |  |
| Decisions not covered | 10/715 = 1% | at most 5% | pass |
| Claims an engine contradicts | 23 | at most 0 | FAIL |
| Parts assigned to the wrong type in the reference | 3 |  |  |

## Per engine

| | strata | ds4 | hyperqwen | ninfer | splash |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 246 | 116 | 115 | 104 | 134 |
| Plainly covered | 93% | 89% | 80% | 90% | 87% |
| Not covered | 0% | 1% | 3% | 1% | 2% |
| Contradicted claims | 3 | 7 | 4 | 7 | 2 |
| Relaxed `should` rules not yet noted | 0 | 0 | 1 | 0 | 0 |
| Inventory entries the source corrects | 4 | 1 | 1 | 3 | 2 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 220 | 20 | 0 |
| rater-b | 207 | 33 | 0 |

## Disagreements on type

- hyperqwen/pool-layout-planner: reference state-pool; rater-a memory-planning, rater-b state-pool — rater-a: Choosing page geometry and block sizes per kind of state is a state-pool sizing choice made at startup. | rater-b: Page geometry fits state-pool, but computing how many requests can be admitted is planning.
- splash/thinking-budget: reference output-constraint; rater-a output-constraint, rater-b output-interpretation
- ninfer/expert-priority-table: reference calibration; rater-a calibration, rater-b residency-policy

## Wrong assignments

- strata layer-kernels: layer-compute (also recurrent-state-store) -> layer-compute, with positional-state-store as a further also. The part owns per-position indexer keys (indexer_keys) at fixed device addresses; that is the indexed per-position state positional-state-store names, and neither assigned type covers holding it.
- strata kv-store: positional-state-store -> positional-state-store, with state-tiering as also. With streaming on it always writes a host copy and keeps only a window of positions in fast memory, bringing selected blocks back before attention reads them; that is moving per-sequence state to a slower tier and back so longer contexts fit.
- ds4 slot-router: sequence-lifecycle -> sequence-lifecycle, with prefix-reuse as an also type. Its main job is choosing the slot whose live state is the longest reusable prefix through ordered reuse tiers, and falling back to the disk store; that is prefix-reuse's job (which store is used when several hold a match), which the reference does not record as a second type.

## Contradicted claims

- strata [layer-compute] output-head: Unless an approximation that was explicitly turned on is in effect, the sequence of layers and operations the model defines is kept; only the order of accumulation inside one operation may vary.
    evidence: Correction (round3): on the pack path, the default when the --native preset is not given, the mixed activation is quantised to 8-bit q8_K before the vocabulary projection (src/core/layer.cpp:1425). Nothing turns this on explicitly; it is the path's default.
    fix: Unless an approximation turned on explicitly, or as a default recorded with the run's settings, is in effect, the sequence of layers and operations the model defines is kept; reduced activation precision inside a kernel counts as such an approximation, and otherwise only the order of accumulation inside one operation may vary.
- strata [prompt-preparation] prompt-builder: effect_on_output defines: when it corrects the template, injects text, shortens input, or tokenizes in pieces
    evidence: The part shortens the output limit to the room left in the context minus a margin instead of refusing, and maps an absent, zero or negative limit to the rest of the context; that decides where output stops. No listed case covers setting the output limit.
    fix: defines: when it corrects the template, injects text, shortens input, sets or shortens the output limit, or tokenizes in pieces
- strata [resource-governing] host-memory-admission: A grant of memory never takes the engine over its limit.
    evidence: When available RAM (which includes the operator's --ram-keep-gib) is below the arena's need and the fallback is not allowed because the operator fixed the choice by hand, the arena is loaded anyway with a warning; only a hard (cgroup) limit refuses (include/strata/core/ple_residency.hpp:50-65, verdict Warn).
    fix: A grant of memory never takes the engine over a hard limit; a soft figure (available memory, an operator's keep-free amount) is exceeded only on the operator's explicit choice and with a warning.
- ds4 [prefix-reuse] disk-kv-checkpoint-store: state: the index of stored prefixes
    evidence: No index is kept; the checkpoint directory is rescanned on every lookup and each file header carries model id, quant bits, context and hit counts (inventory decisions; ds4_kvstore.c).
    fix: state: the stored states with what each is valid for and its retention score, and an index of them where one is kept
- ds4 [request-front] http-api-server: must: A request is not accepted from a caller who is not allowed.
    evidence: ds4-server has no authentication or caller check of any kind (no key, token or Authorization handling in ds4_server.c); it binds 127.0.0.1 by default and with --host accepts every caller that can reach the port.
    fix: must: A request is accepted only from callers the deployment allows; where the engine itself has no caller check, it says so and relies on where it listens.
- ds4 [request-front] http-api-server: state: connections and stored responses
    evidence: Durable response state is rejected; clients must replay input, so no responses are stored.
    fix: state: connections, and stored responses where the engine offers them
- ds4 [resource-governing] power-throttle: takes: requests for memory, what the system reports about pressure; gives: grants and refusals, requests to holders to give memory back; state: what each holder has and what is reserved
    evidence: The part takes only an operator percentage and its own measured work times, gives nothing but sleeps inserted after layers and tokens, and keeps a smoothed per-layer prefill time and decode token time (ds4.c 17955-17994).
    fix: takes, gives and state stated per form: for memory, requests, pressure, grants and holdings; for duty cycle, the target level and measured work, inserted idle time, and the smoothed work measure
- ds4 [row-source] engram-row-reader: state: row cache
    evidence: The reader keeps only the last-tokens history the row numbers are hashed from; it reads through an uncached descriptor (F_NOCACHE / no read-ahead) and has no row cache of its own; any caching is the OS page cache filled by engram-prewarm (ds4_engram.c 110, 154, 380-384). ngram-row-reader likewise keeps only n-gram history.
    fix: state: the recent-token history row numbers are computed from, and a row cache where the engine keeps one
- ds4 [sequence-lifecycle] session-timeline: must: The record of committed tokens always matches the state held for the sequence.
    evidence: On any failure the session is only flagged invalid and its token list no longer describes the state; the guarantee kept is that validity is never claimed for a token list whose state was not fully computed, and the caller re-syncs from tokens.
    fix: must: The record of committed tokens matches the state held for the sequence, or the sequence is marked invalid and its state is not read until rebuilt.
- ds4 [session-persistence] session-payload-serializer: summary: Write a sequence's whole state to a file and read it back, on request.
    evidence: Payloads are written and loaded automatically by the disk checkpoint store when slots are repurposed, on cold and continued stores, and on prefix hits, not only on an explicit save request.
    fix: summary: Write a sequence's whole state to a file and read it back, on request or when a store of reusable state asks for it.
- hyperqwen [draft-policy] verify-length-controller: state: estimates of acceptance and cost
    evidence: Owns only the previous step's want flag, a sticky countdown and a pinned copy of the lookup flags; it keeps no estimate of acceptance or cost.
    fix: state: the signals it decides from: estimates of acceptance and cost, or mode flags and countdowns
- hyperqwen [draft-policy] drafter-free-chains: state: estimates of acceptance and cost
    evidence: Owns a host-side engaged-or-not state machine; entry and exit are by match and first miss, no estimate.
    fix: state: the signals it decides from: estimates of acceptance and cost, or the current mode and what ends it
- hyperqwen [recurrent-state-store] recurrent-state-store: with what is needed to go back: snapshots, a second copy, or a commit deferred until acceptance is known
    evidence: Rollback uses one state slot per draft position, written during the verify block; the next step continues from the slot of the accepted index. None of the three named means.
    fix: with what is needed to go back: snapshots, a second copy, one slot per proposed position, or a commit deferred until acceptance is known
- hyperqwen [state-tiering] kv-offload-tier: Move per-sequence state out of fast memory to a slower place and back, so that more sequences or longer contexts fit.
    evidence: It copies blocks already evicted from the pool and restores them on a later prefix hit or after preemption; its purpose is to avoid recomputation, not to let more sequences or longer contexts fit.
    fix: Move per-sequence state out of fast memory to a slower place and back, so that more sequences or longer contexts fit, or so that state evicted from fast memory is restored instead of recomputed.
- ninfer [configuration] configuration: effect_on_output: exact in itself; rounding / resampled / approximate when it turns on a setting with that effect
    evidence: the inventory records that configuration supplies the sampling defaults ([generation] section) and that they change output; a sampling default is a 'defines' effect and no listed case covers it
    fix: add: defines, when it sets the default of a setting whose own effect is defines (sampling settings, output limits, template options)
- ninfer [draft-proposal] mtp-drafter: effect_on_output: rounding when the number of proposals sets the width of the checked block and the arithmetic depends on that width
    evidence: the checked block has K+1 rows per sequence (K up to 5; up to 15 for the block drafters); with several sequences the step's token count crosses the limit above which AllowA4 weights take 4-bit activations, so the proposal count can change precision, not only rounding (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55)
    fix: rounding, or approximate where the width of the checked block selects a reduced activation precision the weights permit
- ninfer [draft-verification] draft-acceptance: effect_on_output: rounding when the checked block is computed by another path than single-token decoding
    evidence: the verify block's path can quantise activations to 4 bits where single-token decoding keeps 16-bit activations (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55); greedy results then follow a different precision, not only different rounding
    fix: rounding when the checked block is computed by another path; approximate when that path runs at a reduced activation precision the weights permit
- ninfer [layer-compute] layer-compute: must: Unless an approximation that was explicitly turned on is in effect, the sequence of layers and operations the model defines is kept; only the order of accumulation inside one operation may vary.
    evidence: without any run-time setting, AllowA4 weights quantise activations to NVFP4 when a step has more tokens than a per-shape limit and keep BF16 activations below it; the permit is fixed in the model files by the converter and has no run-time switch (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55), so more than accumulation order varies with the step's width
    fix: Unless an approximation that was turned on (at conversion or at run time) and recorded is in effect, the sequence of layers and operations is kept; besides accumulation order only activation precision within the weights' recorded permits may vary, under stated conditions
- ninfer [prompt-reading] chunked-prefill: must: Unless an approximate path that was explicitly turned on is taken, the state it leaves is the state of that prompt up to rounding, whatever the chunking.
    evidence: chunks above the per-shape token limit run 4-bit activations on AllowA4 weights while a final remainder of a few tokens, or token-by-token reading, runs 16-bit activations, so two chunkings of one prompt differ by activation precision, not only by rounding (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55)
    fix: ...the state it leaves is the state of that prompt up to rounding, or up to the reduced activation precision the weights permit for wide chunks, whatever the chunking
- ninfer [step-execution] rank-program: effect_on_output: rounding when sequences sharing a step changes the arithmetic of a row; approximate when it runs a variant that omits work or alters selection
    evidence: the same projection is routed to 4-bit activation quantisation above a per-shape token count and to 16-bit activations below it (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55); the width of the step, not an omitted operation, changes the precision
    fix: approximate when it runs a variant that omits work or alters selection, or when the width of the step selects a reduced activation precision the weights permit
- ninfer [step-scheduler] request-scheduler: effect_on_output: rounding when which sequences share a step, or where it cuts a prompt into chunks, changes the arithmetic of a row
    evidence: the number of tokens in a step selects the activation precision of NVFP4 projections whose weights carry the AllowA4 permit (set by the official recipes): 16-bit activation kernels up to 4 or 16 tokens depending on shape, 4-bit quantised activations above (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55). Batching up to 8 requests, each with K+1 verify rows, can move a row from 16-bit to 4-bit activations: a precision change, not last-bit rounding
    fix: add: approximate, when the number of rows it puts in a step selects a reduced activation precision that the weights permit
- splash [memory-planning] streamed-parts-planner: takes: what the machine reports as free
    evidence: inventory must_never 'rest any size on the host's free memory; only the engine limit counts'; memory-plan takes the device's recommended working set and physical memory (a capacity), not free memory. Free memory is read only at run time by memory-governor.
    fix: takes: what the machine reports as its capacity or as free
- splash [model-loading] model-inspection: effect_on_output: exact / rounding / resampled / approximate, the approximate case being 'weights the full model computes with are quantised or otherwise reduced while loading'
    evidence: runtime/model/RopeScaling.hpp:12-23 YaRN is static, every request short or long takes the same factor; server/serve_options.py:487-491 says it 'changes answers at every length' and is turned on when --max-context exceeds the native window. The node's own choice 'whether the model's positional range is extended beyond its trained length' changes output and no listed case covers it.
    fix: add 'approximate: it extends the model's positional range, where the extension changes the computation for every length'

## Relaxations

- hyperqwen [memory-planning] memory-budget-planner: A size the operator fixes by hand is checked against what was measured, or reported as unchecked. — An operator-pinned pool is not checked; besides an out-of-memory on the first batch, on one platform the over-full pool silently spills to system memory and runs several times slower with no error, which the relaxed text does not mention.

## Inventory errors

- strata window-loop.output_effect_when: recorded 'bit_exact when default configuration; approximate when ... a route tail skip rank is set'; source shows 'The route tail skip is on by default on CUDA serving (rank 7) unless at least 90% of experts are in the GPU cache or the experts are NVFP4, and it changes the output (src/program/generate.cpp:12776-12822; src/core/expert_source.cpp:4964; docs/QUANTS.md:158). The default configuration is not bit_exact.'
- strata expert-dispatch.decisions: recorded 'A missed expert that every token of the window routes only at this rank or lower is neither fetched nor computed; tail skip described as default on the CUDA serving path'; source shows 'The default is conditional: off when the share of experts in the GPU cache reaches STRATA_TAIL_SKIP_MAX_CACHED (default 90%, 60 on a HIP layer split) and off for NVFP4 experts; the start-up message says which applies (src/program/generate.cpp:12787-12822). That condition is a decision of its own.'
- strata engine-command-loop.output_effect_when: recorded 'approximate when Batch slots on, sampled decoding, with a move between the solo path and a slot'; source shows "Sampled rows in batch slots use the solo window's counter-based draw Philox(seed, position) (docs/BATCHING.md:623-624); a move changes only the logits' rounding, which can flip a draw. Nothing approximates the computation."
- strata slot-scheduler.output_effect_when: recorded 'approximate when Sampled decoding with a move between the solo path and a slot'; source shows 'Same as engine-command-loop: the draw is keyed by seed and position on both paths (docs/BATCHING.md:623-624); the difference is rounding of the logits, not an approximation.'
- ds4 pipeline-parallel.output_effect: recorded 'numeric, when activations are sent as f16 or fp8 instead of f32'; source shows 'ds4_distributed.c 790-793, 949-955: the 8-bit wire format is FP8 E4M3, a lossy reduction beyond last bits, so the effect is changes_output for 8 bits (f16 alone is numeric); default is 32 bits (line 65).'
- hyperqwen image-encoder.output_effect: recorded 'none'; source shows "The launcher passes an image processor size limit (longest_edge 2,097,152 pixels, launcher_common.sh:169-173), so larger images are resized down before encoding; the pixel cap decides the model's input, which is changes_output (defines), not none."
- ninfer layer-compute.output_effect: recorded 'numeric; activations may be quantized to 4 or 8 bits where a weight use allows it'; source shows "4-bit activation quantisation changes computed precision, not last bits, so the level is changes_output, and whether it happens depends on the step's token count (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55)"
- ninfer request-scheduler.output_effect: recorded 'none'; source shows 'the rows it puts in a decode or verify round decide whether AllowA4 projections run with 16-bit or 4-bit activations (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55), so round membership changes output'
- ninfer chunked-prefill.output_effect_when: recorded 'state after chunked reading can differ in the last bits from a different chunking or from token-by-token reading'; source shows 'wide chunks run 4-bit activations while token-by-token reading and small remainder chunks run 16-bit activations (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; src/ops/linear/swiglu/nvfp4/dgx_spark/shapes/n12288_k4096.cu 15-58; tools/convert/official_recipes.py 159, 185, 324, 427 (AllowA4 permits); src/models/common/bindings.cpp 43-55); the difference is precision, not last bits'
- splash model-inspection.output_effect: recorded 'none'; source shows 'runtime/model/RopeScaling.hpp:12-23 and server/serve_options.py:487-491: when YaRN is turned on (--max-context past the native window) the static factor changes output at every length (changes_output)'
- splash document-renderer.output_effect: recorded 'none'; source shows 'server/documents.py:133-153 extracts the page text and renders each page at a scale chosen from the page-pixel limit, so the text and pixels the model sees are decided here (changes_output, defines)'

## Decisions not covered

- strata [output-interpretation] request-runner: a ping is sent on the response stream when nothing has gone out for a set time
    missing (timing): keep-alive signal on a response stream while generation produces nothing to send (named only under request-front)
- ds4 [draft-policy] dspark-scheduler: time-based judgement off by default (count-only decisions)
    missing (policy): whether its decisions may use measured elapsed time or only counts, given that time-based decisions make runs irreproducible
- hyperqwen [calibration] calibration-data-capture: Run eagerly so module hooks see inputs
    missing (policy): whether a measurement runs the optimised serving path or a slower instrumented path that exposes internal values
- hyperqwen [engine-supervision] engine-core-loop: Async scheduling overlaps planning of the next step with execution of the current one
    missing (timing): whether the process loop prepares the next step while the current one runs on the device
- hyperqwen [model-conversion] model-dir-publisher: Backup suffix per step so steps sharing a shard keep separate pristine copies
    missing (policy): whether conversion rewrites files in place, and whether and how pristine originals are kept per step
- hyperqwen [step-execution] model-runner: Keep a blocking read as the barrier between steps under async scheduling
    missing (timing): how host-side input buffers of consecutive steps are kept apart: a barrier before reuse, or one buffer per step in flight
- ninfer [layer-compute] layer-compute: the encoding in which the computation writes per-position attention state (KV encoding)
    missing (format): the precision and layout in which the computation writes the per-position state it appends
- splash [layer-compute] target-forward: GDN value-head order
    missing (format): the order of heads or channels the kernels compute in, where it differs from the model's published order
- splash [positional-state-store] draft-state: cache the window, not the ring
    missing (policy): whether derived per-position state is kept for reuse, or only the inputs it is recomputed from
- splash [positional-state-store] draft-state: rebuild the ring in the next prefill chunk after a restore
    missing (timing): when derived per-position state is rebuilt after a restore

## Decisions covered loosely

- strata [configuration] run-config-generator: an argument that differs from what setup last wrote counts as a hand edit and is kept across rewrites, except options setup re-decides
    nearest: operator values, presets, measured values and defaults
- strata [draft-policy] draft-policy: which window sizes a lookup or chained window may use, and dropping a size for the rest of the process when its graph finds no device memory
    nearest: limits on the round
- strata [draft-proposal] lookup-drafter: most recent end positions kept per trigram in the lookup index
    nearest: how a lookup source matches earlier text, and how far back it searches
- strata [draft-verification] draft-verifier: the exact gated acceptance rule is used only under listed configuration conditions; otherwise an older rule runs with a warning that the distribution is off
    nearest: the acceptance rule under sampling
- strata [draft-verification] draft-verifier: a one-row window advances state inside the window graph and launches no separate commit
    nearest: how each kind of state is committed or undone
- strata [layer-compute] layer-kernels: order of kernels within a layer, split into halves around the host-supplied expert rows
    nearest: how independent operations are ordered to overlap with work on another device
- strata [layer-compute] output-head: the head runs inside the window graph in column chunks for long windows, or after the layer loop followed by a sync, full logits read-back and non-finite scan
    nearest: whether results are checked for non-finite values, and what is done then
- strata [memory-planning] startup-memory-sizing: lowest value the reserve may be lowered to so that the minimum cache fits
    nearest: the order in which things are given up when memory is short, and when starting is refused
- strata [memory-planning] host-memory-admission: the engine may swap the expert arena for the file source on its own unless the operator fixed the RAM choice by hand
    nearest: an operator's explicit size against the computed one
- strata [model-loading] expert-layout: native per-layer layout when its table file exists, else the canonical layout with one blob size
    nearest: which stored encoding of a tensor is loaded when the files carry more than one, and which kernels accept it
- strata [prefix-reuse] resume-decision: reuse of any kind is enabled only when checkpoint capacity is above zero
    nearest: how many are kept and where
- strata [prefix-reuse] parked-conversations: host memory budget of the parked store: operator value or a computed share of available memory with cap, rounding and floor
    nearest: how many are kept and where
- strata [row-source] ngram-reader: keep-alive reads of one random page while idle in direct mode, until a time after the last request
    nearest: warming the table in the background and when to stop
- strata [sequence-lifecycle] slot-scheduler: how often a running prompt read gives way to a waiting request with a much shorter prompt
    nearest: the order in which waiting prompts are read, and whether several are read together
- strata [step-execution] window-loop: per window, a device-only plan variant when every expert of the stage is resident, else a variant that consults the host each layer
    nearest: which kinds of step are replayed from a recorded graph and which are launched directly
- ds4 [calibration] imatrix-collector: minimum samples per expert before an entry counts as covered
    nearest: the rule that accepts or rejects a measured result
- ds4 [device-backend] gpu-backend: prefill workspace shared between sessions in server batch mode
    nearest: scratch and command buffers
- ds4 [draft-policy] dspark-scheduler: longer pauses after rounds with no draft
    nearest: when drafting pauses and resumes
- ds4 [expert-cache] routed-expert-cache: cache buffers locked in memory; a lock failure lowers the effective limit
    nearest: what is done when the cache cannot be allocated at its planned size
- ds4 [memory-planning] ssd-cache-planner: a user-given cache size is a target, not a guarantee
    nearest: a hard limit against a soft figure that may be exceeded with a warning
- ds4 [model-loading] model-loader: shared mapping for GPU backends, private mapping for the CPU backend
    nearest: map the file in place or copy into memory
- ds4 [residency-policy] expert-eviction-policy: heat counts every selection, misses as well as hits
    nearest: the replacement rule
- ds4 [residency-policy] expert-cache-preloader: preload cap in automatic mode
    nearest: what the cache holds before any request
- ds4 [row-source] engram-prewarm: warm only when model, runtime, table and a reserve fit physical memory
    nearest: warming the table in the background and when to stop
- ds4 [row-source] ngram-row-reader: prefetch only for chunks above a size and within a buffer cap
    nearest: prefetching rows for coming or drafted tokens
- ds4 [sampling] tool-call-sampling-mode: which tag sets count as structure
    nearest: whether settings change per position, for example greedy on structure and sampled on content
- ds4 [session-persistence] session-payload-serializer: under tensor parallelism load only tokens and re-prefill
    nearest: in which configurations saving and restoring is offered
- hyperqwen [configuration] launch-profile-resolver: Drafter kind and number of draft tokens
    nearest: named profiles and what each fixes
- hyperqwen [configuration] launch-profile-resolver: Pin the pool by bytes or by utilisation; skip the pin under tensor parallelism
    nearest: whether an operator value is a hard limit or a target
- hyperqwen [configuration] launch-profile-resolver: Prefix caching on with align-mode recurrent state, and the snapshot retention interval
    nearest: rules that derive a setting's default from other settings and machine facts
- hyperqwen [draft-policy] verify-length-controller: Take the long block unconditionally below a context length
    nearest: whether the round's width is chosen from each proposal's probability and the measured cost of each width
- hyperqwen [draft-proposal] mtp-drafter: Draft from the target's top-k/top-p support; optional draft temperature scale
    nearest: the set of tokens proposals are restricted to (proposal temperature not named)
- hyperqwen [draft-verification] draft-acceptance: Draft sample method must be probabilistic so q is passed
    nearest: the acceptance rule under sampling
- hyperqwen [graph-capture] compile-and-warmup: Which kernel rungs and spec-shaped dummy verifies to run at boot
    nearest: which step shapes are recorded ahead and which on first use (names recording, not warm-up compilation)
- hyperqwen [layer-compute] full-attention-compute: int8-QK prefill only for one-request chunks over 16 tokens on the exact geometry with bf16 KV
    nearest: activation precision inside kernels (the conditions gating a reduced-precision kernel per step are not named)
- hyperqwen [layer-compute] full-attention-compute: Sparse attention budget when sparse attention is on
    nearest: any deliberate change to the model's arithmetic (its size or budget is not named)
- hyperqwen [model-conversion] offline-weight-requantizer: Bit width per tensor group and group size
    nearest: precision per kind of weight (bit width yes; quantisation group size is not named)
- hyperqwen [model-conversion] draft-vocab-builder: Which extra scripts are appended and under what row budget
    nearest: the data a derived piece is selected or fitted from, and what is eligible for it (forced inclusion beyond the counted data and its budget not named)
- hyperqwen [model-conversion] gptq-requantizer: Bits and group size; no act-order so the kernel needs no index
    nearest: precision per kind of weight (quantisation method options constrained by the run-time kernel not named)
- hyperqwen [model-partitioning] tensor-parallel: Allocator without expandable segments so graph buffers can be exported between processes
    nearest: which other engine features may be combined with splitting the model, and which are refused
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Flush a finished request's full block but discard a partial one
    nearest: when state held in a staging precision is converted to its stored format
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Keep retired sinks resident; evict oldest first only when slots run dry
    nearest: which positions are kept at higher precision than the stored format (eviction of the staging area not named)
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Draft passes after the first only allocate slots, never flush
    nearest: when state held in a staging precision is converted to its stored format (not tied to positions that may still be rejected)
- hyperqwen [request-front] access-guard: Let only a real CORS preflight skip the token
    nearest: who is allowed and how
- hyperqwen [sampling] sampler: One top-k instead of a full-vocabulary sort when every request's top-k is small
    nearest: the kernel used for the sampling arithmetic, and how it changes with the number of rows (changes with the settings, not rows)
- hyperqwen [state-tiering] kv-offload-tier: Which groups count as draft attention
    nearest: which kinds of state the slower tier holds
- ninfer [expert-dispatch] hybrid-moe-dispatch: large-work versus small-work handling of a layer (stream the whole layer or split with the CPU) by a token-count threshold
    nearest: the share of misses fetched now against left to another device
- ninfer [media-preparation] media-preparer: preprocess cache capacity and live payload budget
    nearest: caching of prepared media and its key
- ninfer [model-loading] shard-materializer: whether a rank's slice of an encoded tensor can be expressed value-preservingly, else the format refuses it
    nearest: whether weights are re-encoded at load and how
- ninfer [prefix-reuse] context-resource-manager: a cross-rank copy is a candidate only when recompute cost was measured and the copy is cheaper
    nearest: when restoring is refused in favour of reading again
- ninfer [prefix-reuse] context-resource-manager: choice of the attention-owner rank for a request by load balance, then longest local prefix
    nearest: which device restored state is placed on
- ninfer [request-front] http-api: which protocol fields are accepted or rejected (for example audio history)
    nearest: which per-request controls a caller may set
- ninfer [residency-policy] offload-mode-switch: refill pace of the extra cache after a return to small work (bytes and batches per call)
    nearest: the gain a change must bring, and a limit on changes per round
- ninfer [sequence-lifecycle] model-session: a full permit reserved before verification that already covers the later commit peak
    nearest: a sequence's state allocated up front or grown on demand
- ninfer [step-execution] rank-program: where host handoffs split device work inside a unit (grammar mask, CPU experts, final acceptance)
    nearest: cutting a step into parts so that work on two devices overlaps
- splash [calibration] ane-ffn-calibrator: the minimum predicted gain to enable the split
    nearest: the rule that accepts or rejects a measured result (validity of a measurement, not the gain threshold for turning a feature on)
- splash [configuration] configuration: defaults for each flag (decode share, idle release, formats, verify rows, disk quota, ANE)
    nearest: which settings that change output are on by default, and in which profile (only output-changing settings; no choice names the default value of every setting)
- splash [draft-policy] verify-row-budget: refit interval, label window, decay, prior strength
    nearest: how fresh the signals it decides from must be (does not name how the acceptance and cost estimates are fitted)
- splash [expert-cache] expert-store: release one chunk, or all to floor under critical pressure
    nearest: which part is released or regrown first under memory pressure (which part, not how much per pressure level)
- splash [model-loading] weight-layout-planner: which formats are accepted and kept native versus converted
    nearest: whether weights are re-encoded at load and how (covers native versus converted, not which source formats are accepted)
- splash [output-interpretation] output-parser: hold text that may begin a stop string
    nearest: stop conditions and their order (the holding is the must rule, no choice names how much is held or when it is released)
- splash [prefix-reuse] composite-state-cache: retire rolling checkpoints once a newer one is published
    nearest: what earns stored state its retention (does not name retiring an entry that a newer one supersedes)
- splash [prompt-reading] prefill-runner: abandon a paused command for higher-priority work (nothing committed)
    nearest: what state is kept when reading is interrupted or cancelled (consequence, not when reading may be preempted)
- splash [residency-policy] slot-recycler: scans leave no ghosts and move no hits
    nearest: the replacement rule (does not name protecting the cache against one-pass bursts of use)
- splash [resource-governing] memory-governor: pool growth admitted on its net change when cache funds it
    nearest: when holders that gave memory back may grow again (timing, not how a growth that displaces cache is counted against the limit)
- splash [sampling] token-selector: sampling policy per lane
    nearest: whether settings change per position (per position, not per sequence within one shared step)
- splash [state-tiering] write-behind: minimum depth and delay before copying
    nearest: copying ahead of need (does not name the conditions an entry must meet before it is copied ahead)
- splash [state-tiering] kv-spill-controller: keep dense history, tail window and in-flight prefill groups Full
    nearest: what leaves first (does not name which positions of a moved sequence must stay in fast memory)
- splash [step-scheduler] request-scheduler: group commands run in layer passes
    nearest: sequences and rows per step (does not name grouping several prompt chunks into one step run layer by layer)
- splash [telemetry] telemetry: log only transitions
    nearest: what is recorded by default and what on request

