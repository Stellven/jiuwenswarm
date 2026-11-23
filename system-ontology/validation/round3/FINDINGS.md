# Node types draft 0.3: independent checks, round3

44 types, 329 choices. Thresholds were fixed on 2026-11-16 in `validation/criteria.yaml`, before this draft was written.

| Check | Result | Threshold | |
|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 231/240 = 96% | at least 90% | pass |
| Decisions plainly covered by a choice | 485/702 = 69% | at least 80% | FAIL |
| Decisions covered only loosely | 156/702 = 22% |  |  |
| Decisions not covered | 61/702 = 9% | at most 5% | FAIL |
| Claims an engine contradicts | 41 | at most 0 | FAIL |
| Parts assigned to the wrong type in the reference | 11 |  |  |

## Per engine

| | strata | ds4 | hyperqwen | ninfer | splash |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 241 | 113 | 111 | 104 | 133 |
| Plainly covered | 80% | 67% | 63% | 66% | 57% |
| Not covered | 4% | 11% | 8% | 12% | 14% |
| Contradicted claims | 12 | 4 | 10 | 8 | 7 |
| Relaxed `should` rules not yet noted | 3 | 1 | 1 | 2 | 1 |
| Inventory entries the source corrects | 5 | 4 | 2 | 4 | 2 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 211 | 29 | 0 |
| rater-b | 195 | 45 | 0 |

## Disagreements on type

- ds4/prefill-layer-pagein: reference expert-source; rater-a expert-fetch, rater-b expert-fetch — rater-a: It warms the operating system page cache for a mapped file rather than bringing blocks into an expert cache.
- hyperqwen/pool-layout-planner: reference state-pool; rater-a state-pool, rater-b memory-planning — rater-a: It only lays out page geometry and computes admissible capacity at startup; it never hands pages out. | rater-b: Divides the pool into pages and counts admissible requests, which is startup planning but also pool layout.
- strata/engine-command-loop: reference step-scheduler; rater-a engine-supervision, rater-b step-scheduler — rater-a: It runs the engine process loop and also advances batch slots window by window and serialises prompt reads, part of composing steps. | rater-b: Reads commands, runs prompt reads and advances slot windows; it composes windows but does not choose slots, so it is part loop, part scheduler.
- hyperqwen/stall-watchdog: reference engine-supervision; rater-a telemetry, rater-b engine-supervision — rater-a: It detects a stalled engine, which is supervision's job, but only logs a warning and never acts.
- hyperqwen/engine-core-loop: reference step-scheduler; rater-a engine-supervision, rater-b engine-supervision — rater-b: Runs the engine process loop calling scheduler and runner each step; supervision only in part.
- splash/draft-state: reference draft-proposal; rater-a positional-state-store, rater-b positional-state-store
- ninfer/executor: reference device-backend; rater-a step-execution, rater-b step-execution — rater-a: It is a frame and ticket channel to rank programs that orders result delivery and retirement, spanning step execution and device submission. | rater-b: Also delivers retirement signals and frees frames, which is device-backend work.
- ninfer/expert-priority-table: reference calibration; rater-a calibration, rater-b residency-policy
- ninfer/expert-residency-planner: reference residency-policy; rater-a memory-planning, rater-b memory-planning — rater-a: It also chooses the fixed expert set per layer and the CPU/GPU split threshold, which are residency and dispatch decisions.

## Wrong assignments

- strata layer-kernels: layer-compute -> recurrent-state-store (as also). It alone owns the recurrent state, the convolution/lookup history and the indexer keys (owns_state gdn_state, ple_history, indexer_keys); layer-compute has no state, so the second job is uncounted.
- strata host-memory-admission: memory-planning -> resource-governing (as also). It also runs on demand and tells the lookup-table reader to give its lock back when the arena or the conversation cache needs RAM, which is reclaim while running.
- strata engine-command-loop: step-scheduler -> sequence-lifecycle (as also). Besides composing windows it owns the live conversation record and the batch slot table, the record of committed tokens and places that sequence-lifecycle owns.
- ds4 prefill-layer-pagein: expert-source -> expert-fetch. It does not keep the full set obtainable; it warms the next layer's routed-weight pages ahead of need, best effort, which is expert-fetch's 'best-effort warming ahead of need' form, and its mechanism decision is an expert-fetch choice.
- ds4 image-input-encoder: modality-encoding -> modality-encoding, with also: media-preparation. It also decodes PNG/JPEG, enforces size limits and rejects remote and file sources, which is media-preparation's job; two of its three decisions are not covered without that type.
- ds4 network-tensor-parallel: model-partitioning -> model-partitioning, with also: device-communication. It also owns the RDMA/TCP transport, gate exchange of partial sums and gate timeouts; no other ds4 part carries device-communication between machines.
- ds4 pipeline-parallel: model-partitioning -> model-partitioning, with also: device-communication. It also forwards hidden state between machines, owns worker registration and route discovery and reconnection; no other part carries that transport.
- hyperqwen engine-core-loop: step-scheduler -> engine-supervision. It runs the engine's process loop and the transport from the frontend, calling the scheduler once per step without deciding what a step contains, which is exactly what step-scheduler's own 'not' gives to engine supervision; its one decision (async scheduling) belongs to request-scheduler.
- ninfer expert-residency-planner: residency-policy -> memory-planning. it divides the remaining device bytes into fixed region, windows and extra cache, sizes CPU workers and upload slots, and refuses startup when nothing fits; which experts are held follows the priority table, so residency-policy is at most a second job
- splash draft-state: draft-proposal -> positional-state-store. It owns the draft model's per-position ring K/V and the window it is computed from; positional-state-store names a draft model's per-position state explicitly, while draft-proposal declares no state.
- splash kv-page-pool: state-pool -> state-pool, also positional-state-store. Besides handing out and compacting pages it fixes the stored K/V format (INT8 with scales, page forms), which is positional-state-store's choice and the source of its output effect.

## Contradicted claims

- strata [configuration] run-config-generator: effect_on_output level 'approximate' (case 'it turns on a setting that changes output'): 'it needs the requester's permission'
    evidence: Setup writes 8-bit integer K/V by default for any context above 8192 unless the person chooses otherwise; the lossy format is the default, not an opt-in.
    fix: approximate when it turns on a setting that changes output, by default or on request; a default that changes output is recorded as such
- strata [draft-policy] draft-policy: must: 'It changes how much is checked, never the rule by which a token is accepted.'
    evidence: The exact gated acceptance rule runs only without the cost-aware window, without the lookup chain, without DFlash2 and with windows of at most 8 rows; otherwise the verifier falls back to the older rule and warns the distribution is off (draft-verifier decision 3).
    fix: Its per-round choices never change the acceptance rule; a mode of the policy that forces another acceptance rule is stated with that mode.
- strata [draft-policy] draft-policy: effect_on_output: exact or rounding only
    evidence: output_effect_when: distribution_exact when STRATA_SPEC_PROB=1 with the gated rule; under probabilistic acceptance the width and source change the draws but not the distribution.
    fix: add: resampled when acceptance under sampling uses the proposal, so the chosen source and width change the draw but not the distribution
- strata [draft-verification] draft-verifier: effect_on_output: exact 'when greedy decoding with exact agreement'; under sampling only resampled or approximate
    evidence: Sampled requests in the default exact-match mode are bit_exact: each row's draw is keyed by seed and absolute position, and a draft is accepted only when it equals that draw.
    fix: exact when greedy, or when sampling draws each position from a stream keyed independently of the proposal and a proposal is accepted only when it equals that draw
- strata [engine-supervision] engine-client: effect_on_output: exact (only case)
    evidence: Its own choice rewrites a requested top_k outside 1..64 to 64 before sending (serve/server.py:1659), which changes the sampled distribution.
    fix: exact, unless it rewrites request settings it passes to the engine: defines
- strata [expert-dispatch] expert-dispatch: effect_on_output level 'approximate': 'a deliberate change to the computation ... it needs the requester's permission' (case 'approximate when it omits selected blocks')
    evidence: The tail skip that omits low-ranked missed experts is on by default on the CUDA serving path (inventory output_effect_when); docs/QUANTS.md:158 'STRATA_ROUTE_TAIL_SKIP=7, the default since 0.1.42'. No request asks for it.
    fix: approximate when it omits selected blocks; an engine may enable this by default, in which case the omission is recorded with the run's settings and can be turned off
- strata [layer-compute] expert-router: must: 'The sequence of layers and operations the model defines is kept; only the order of accumulation inside one operation may vary.'
    evidence: STRATA_ROUTE_PRIOR re-picks the 10 experts with a residency bonus and STRATA_ROUTE_RESIDENT swaps a tail expert for a resident one: the model's selection is changed, which the type's own choice 'any deliberate change to the model's arithmetic' allows.
    fix: Unless a deliberate change the requester turned on is in effect, the sequence of layers and operations the model defines is kept; only the order of accumulation inside one operation may vary.
- strata [memory-planning] startup-memory-sizing: gives: 'the context length and concurrency the engine can offer'
    evidence: Context length and batch slot count arrive as engine arguments from launch-argument-resolver; this part only sizes the expert cache and prompt buffers from the remainder and never derives either.
    fix: gives: the context length and concurrency the engine can offer, or the check that the requested ones fit
- strata [model-loading] native-weight-loader: effect_on_output: exact when weights are used as stored, rounding only when re-encoding changes floating-point width
    evidence: Choosing the stored GGUF block form over the pack form (both loaded unchanged) switches the head and projections to other kernels; output_effect numeric 'when native head or native projections in use'.
    fix: add: rounding when it chooses among stored encodings of a tensor, which selects other kernels
- strata [prefix-reuse] resume-decision: effect_on_output: rounding when 'state is stored at reduced width, was produced with other chunk boundaries, or batched and unbatched paths round differently'
    evidence: output_effect_when: numeric also when the expert placement differs between the stored state and a cold read (experts computed on the CPU or the GPU round differently); no listed case covers it.
    fix: rounding when the stored state was produced under other rounding than a cold read: reduced width, other chunk boundaries, another batch path, or computation placed on other devices
- strata [prompt-reading] prompt-path: must: 'The state it leaves is the state of that prompt up to rounding, whatever the chunking.'
    evidence: output_effect_when: approximate when the optional approximate late-layer read is on; the type itself lists that approximate case and choice, so the must rule is not kept in that mode.
    fix: Unless an approximate path the requester turned on is taken, the state it leaves is the state of that prompt up to rounding, whatever the chunking.
- strata [row-source] ngram-reader: state: 'row cache and the token history the row numbers are computed from'
    evidence: owns_state is empty; the two-token history is advanced by the driver and the window commit and is ple_history owned by layer-kernels; the reader is handed the window's tokens and the two before them.
    fix: state: row cache; takes: the recent tokens the row numbers are computed from
- ds4 [calibration] expert-locality-profiler: summary: Measure the model or the machine, offline or at startup
    evidence: Records every routing decision per layer during an ordinary inference run (opt-in by environment) and writes the profile and hotlist at the end; it measures neither offline nor at startup.
    fix: Measure the model or the machine offline, at startup, or during an opt-in profiling run, and record results that other nodes take as fixed input.
- ds4 [model-conversion] offline-converter-quantizer: must: An interrupted or mismatched conversion is never left looking complete.
    evidence: gguf-tools/deepseek4-quantize.c 2042, 2793-2856 opens the final out_path with fopen("wb"), writes header and tensor directory first and calls exit(1) on a size mismatch, leaving a partial file under the final name; only the loader's bounds check (ds4.c 2846 'tensor points outside GGUF file') later rejects it. The Python tools write .partial and rename.
    fix: An interrupted or mismatched conversion is never accepted as complete: it is written under a temporary name until finished, or it is rejected when loaded.
- ds4 [resource-governing] power-throttle: must: Where it limits duty cycle, the average over the stated window stays at or below the requested level.
    evidence: ds4.c 17963-17994: sleeps work_avg*(100-p)/p after each prefill layer or decoded token, from an exponential average (0.875/0.125) of past work time, not the current sample; no window is stated and when work time rises the duty cycle exceeds the target until the average catches up.
    fix: should: Where it limits duty cycle, idle time is inserted in proportion to measured work so the duty cycle approaches the requested level; relaxed: one engine estimates work from a moving average and states no window.
- ds4 [step-scheduler] request-scheduler: must: Every admitted sequence is served, or ended with an explicit error within a stated wait.
    evidence: Unbounded FIFO queue, no overload rejection, no wait limit or timeout; decode has strict priority and prefill is admitted only when no decode is pending, so a queued prompt has no stated bound on its wait (only client disconnect or shutdown ends it).
    fix: Every admitted sequence is eventually served or ended with an explicit error; where the engine bounds the wait, the bound is stated.
- hyperqwen [calibration] calibration-data-capture: state: the recorded results and the key that says what they are valid for
    evidence: The capture writes hidden states, token ids and seqs.json (id, src, think, offsets) and Hessians with no record of which target checkpoint, quantisation or build produced them (drafter/capture.py:1-40); owns_state lists only resumable output and a lock.
    fix: state: the recorded results and, where the engine keeps one, the key that says what they are valid for; results without a key are valid only by convention
- hyperqwen [configuration] launch-profile-resolver: effect_on_output: exact in itself; approximate when it turns on a setting that changes output
    evidence: Its own choice of drafter and number of draft tokens changes greedy text through block-width rounding and changes the draw under sampling, which is rounding/resampled, not a deliberate change to computation or stored precision (inventory output_effect_when; context-lookup-proposer and draft-acceptance records).
    fix: add: rounding or resampled when it turns on speculation or another setting whose own effect is at that level; keep approximate for settings that change computation or stored precision
- hyperqwen [configuration] correctness-pins: must: A combination known to give wrong output is refused by default; an operator's override is explicit and recorded.
    evidence: Most known-bad combinations are not refused but silently replaced: adaptive verify length pinned off, FULL capture forced to PIECEWISE, FlashInfer sampler switched off, STICKY limited to one request; only fp16 with a speculator refuses to boot. Nothing records that a pin or an override was applied.
    fix: A combination known to give wrong output is not run by default: it is refused or one member is replaced by a safe setting; an operator's override is explicit
- hyperqwen [draft-verification] draft-acceptance: summary: ...and make every kind of state reflect exactly that prefix; gives: state committed to the accepted prefix
    evidence: The rejection sampler only reports the accepted count; it does not commit or roll back anything. KV of rejected positions is overwritten next step and recurrent state is selected from the per-draft slot by the store using the accepted index (inventory 'not').
    fix: gives: the accepted tokens and the accepted count by which each kind of state is committed, either by this node or by the state's owner
- hyperqwen [engine-supervision] stall-watchdog: summary: ...notice when it stalls or fails, and restart it.
    evidence: The sentinel only logs one warning per stall episode; nothing restarts the engine or handles in-flight requests.
    fix: notice when it stalls or fails, and report it or restart it
- hyperqwen [layer-compute] full-attention-compute: must: The sequence of layers and operations the model defines is kept; only the order of accumulation inside one operation may vary.
    evidence: Opt-in sparse LSA attention attends to a budgeted subset of positions (exact only below about 4.6k tokens), and the int8-QK prefill path quantises Q and K; both change the operation, not only its accumulation order.
    fix: The sequence of layers and operations the model defines is kept; beyond the order of accumulation it changes only through an approximation the operator or requester explicitly enabled
- hyperqwen [layer-compute] linear-gemm: must: The sequence of layers and operations the model defines is kept; only the order of accumulation inside one operation may vary.
    evidence: With VLLM_MARLIN_INPUT_DTYPE=int8 the selected layers quantise activations to int8 per token (batch default: MLP), reported perplexity +0.9 to +3.7 percent.
    fix: same rewording as for full-attention-compute: changes beyond accumulation order only through an explicitly enabled approximation
- hyperqwen [memory-planning] memory-budget-planner: must: The engine does not start serving on a plan that exceeds a hard limit; an estimate found over the limit is corrected or refused first.
    evidence: With the pool pinned by bytes (KV_MEM) the plan is not checked: when pinned too full the first real batch OOMs on Linux, or under WSL2 the allocation silently spills into system RAM and serving continues 3-28x slower.
    fix: A computed plan that exceeds a hard limit is corrected or refused before serving; a size fixed by the operator may bypass the check only as the should rule records
- hyperqwen [modality-encoding] image-encoder: effect_on_output: exact in itself; rounding / approximate by encoder width
    evidence: This part also enforces a pixel cap of 2048 image tokens and one image per prompt, which decides how an image is resized before it reaches the model; the engine has no separate media-preparation part to carry the 'defines' case.
    fix: add: defines when the encoding node itself sets the resolution or token count media is reduced to
- hyperqwen [step-scheduler] request-scheduler: effect_on_output: rounding when which sequences share a step changes the arithmetic of a row
    evidence: Here the scheduler also cuts prompts into chunks within the per-step token budget, and chunk boundaries change rounding (inventory output_effect_when); this engine has no separate prompt-reading part that would carry that case.
    fix: rounding when which sequences share a step, or where a prompt is cut into chunks, changes the arithmetic of a row
- ninfer [calibration] context-cost-calibrator: effect_on_output: exact in itself; rounding only when its results set a split between devices
    evidence: its cost presets decide whether the resource manager restores a checkpoint or recomputes the prefix; the inventory records that a restored prefix was read with other chunk boundaries than a fresh read (context-resource-manager output_effect_when)
    fix: add: rounding when its results choose between restoring stored state and recomputing it
- ninfer [device-backend] executor: summary: choose the kernel variant for this device and step shape, submit, and retire completed work
    evidence: the executor accepts units into frames, passes them to rank programs and delivers result, commit and retirement events; kernel variants are chosen by registered shape profiles in the ops (layer-compute decisions)
    fix: Submit a step's work to the devices and report results and retirement in order; the kernel variant is chosen here or by the computation
- ninfer [engine-supervision] rank-launcher: summary: ... notice when it stalls or fails, and restart it
    evidence: on failure it stops submission and kills the remaining processes; any uncaught error fails all requests and stops the worker; no restart path exists in src
    fix: ...notice when it stalls or fails, and restart it or stop it with every request ended
- ninfer [modality-encoding] vision-encoder: state: cache of encoded media
    evidence: keeps features only in a window lease until the matching text spans consume them; no cache of encoded media (src/models/common/vision has no cache)
    fix: encoded media held until consumed, and a cache of it where one exists
- ninfer [model-conversion] draft-head-builder: effect exact when: it only re-arranges bytes, or changes only pieces used for proposals that the full model checks
    evidence: acceptance under sampling accepts draft i with probability p_i(draft_i) and samples the first rejection from p with the draft removed (include/ninfer/ops/speculative_accept.h 22-44; inventory draft-acceptance output_effect_when); a different draft head gives different proposals and so a different realised token sequence for the same seed
    fix: exact when it only re-arranges bytes, or changes proposal-only pieces under greedy decoding; resampled when it changes proposal-only pieces and acceptance under sampling uses the proposals
- ninfer [residency-policy] offload-mode-switch: summary: Decide which selectively used weights are kept in fast memory, at startup from a ranking or while running from use.
    evidence: it changes the reusable region while running from the token count of each execution, not from use (inventory not: 'reacts to work size, not to which experts were used'); none of the three forms covers it
    fix: ...at startup from a ranking, or while running from use or from the size of the work; add a form 'switched by work size between extra cache and streaming windows'
- ninfer [residency-policy] offload-mode-switch: takes: how often each is used, or a ranking made offline
    evidence: takes the token count of the execution and the planner's layouts and thresholds
    fix: how often each is used, a ranking made offline, or the size of the coming work
- ninfer [residency-policy] offload-mode-switch: state: use counts or the ranking
    evidence: owns the current region mode and refill progress
    fix: use counts, the ranking, or the current role of each region and its refill progress
- splash [model-conversion] model-installer: Offline, turn the published model into the files this engine reads: weights in the engine's layout and precision, and any derived pieces
    evidence: The installer converts no weights and writes no prepared copy; it pins snapshots and publishes an assembly of links plus a digest record. Conversion into kernel layout happens at every start in weight-image-loader (absent: offline weight conversion).
    fix: Offline, obtain, pin and record the published model and any derived pieces the engine reads; weights are put in the engine's layout and precision here when conversion is offline, otherwise at load.
- splash [model-loading] weight-image-loader: summary: 'At startup, open the model's files ...'
    evidence: Images are rewritten from source again on demand when weight-residency restores weights after an idle release (runs: startup, on_demand).
    fix: At startup, and again whenever released weights are restored, open the model's files, check them and make the weights every token uses readable.
- splash [model-loading] weight-image-loader: effect_on_output: approximate when weights are quantised or otherwise reduced while loading
    evidence: The draft is quantized from BF16 to 4-bit at load; this changes proposals only, which the full model checks: greedy output is unchanged and sampled output keeps its distribution.
    fix: approximate when weights the full model computes with are quantised while loading; quantising weights used only for proposals is exact under greedy decoding and resampled under sampling.
- splash [recurrent-state-store] gdn-state-cells: Hold state that is fixed in size and overwritten as the sequence advances, with the snapshots needed to go back. gives: a snapshot to restore from
    evidence: Verify never advances the cell; acceptance records pending rows and swaps the parity of two cells, and the next step folds the taped rows in. Going back needs no snapshot.
    fix: Hold state that is fixed in size and overwritten as the sequence advances, with what is needed to go back: snapshots, a second copy, or a commit deferred until acceptance is known.
- splash [secondary-compute] ane-ffn-split: Compute a share of a layer's work on a second device, from weights that device can read where they lie.
    evidence: The ANE's int8 weights are requantized by the GPU one layer ahead into shared surfaces; the second device does not read them where they lie.
    fix: Compute a share of a layer's work on a second device, from weights it can read where they lie or that are prepared for it ahead of the layer.
- splash [state-pool] kv-page-pool: effect_on_output: exact
    evidence: The pool stores K/V as INT8 with per-token scales by default (changes_output against --kv-format bf16); its page forms also fix stored precision.
    fix: exact in itself; where the pool also fixes the stored format, approximate when state is stored quantised (or assign the format to positional-state-store).
- splash [state-tiering] kv-spill-controller: effect_on_output: exact when state comes back as it left; rounding when held at another precision
    evidence: A spilled request's output is bounded by the tier's active-KV quota and the request is ended at that bound (Engine.hpp:145-158, 429, 641); no listed case covers ending output.
    fix: add: defines, when the slower tier's capacity bounds how long a sequence may grow and output is ended at that bound.

## Relaxations

- strata [calibration] speed-calibration: A recorded result is used only where its validity key matches the model, machine and build. — A preset is still applied, with a re-check only offered, when the engine's tuning epoch, the driver or the preset's age changed.
- strata [memory-planning] startup-memory-sizing: A size the operator fixes by hand is checked against what was measured, or reported as unchecked. — An explicit --expert-cache N is kept as asked; the after-allocation re-read of free memory against the reserve applies only to the automatic cache, so an explicit size is checked only by whether the allocation succeeds.
- strata [prompt-reading] prompt-path: Where chunk boundaries change stored state, the chunking is part of the key under which that state is reused. — Resume points and checkpoints change the chunking of the prompt read (resume-decision, checkpoint-chain: numeric), but the reuse key is token ids, image keys and the steering flag only.
- ds4 [prompt-reading] prompt-prefill-driver: Where chunk boundaries change stored state, the chunking is part of the key under which that state is reused. — The prefill quantum changes with load (small while any generation is active, larger otherwise) and chunk size fixes compressor-row finalisation, yet disk checkpoints are keyed by a hash of rendered text with model id and quantization only; the engine aligns store boundaries to a fixed multiple instead of keying on the chunking.
- hyperqwen [calibration] calibration-data-capture: A recorded result is used only where its validity key matches the model, machine and build. — No validity key exists: captured hidden states, Hessians and self-generated tokens are reused by the GPTQ requantizer and the vocabulary builder for whatever target directory they are pointed at; the type's relaxed note (stale presets, compiled-in figures) does not describe this.
- ninfer [calibration] context-cost-calibrator: A recorded result is used only where its validity key matches the model, machine and build. — the preset key is the hardware class and the model's prefill signature; the CUDA driver and runtime versions are recorded in the report but not part of the key (bench/context_cost/context_cost_bench.cpp 357-497)
- ninfer [prompt-reading] chunked-prefill: Where chunk boundaries change stored state, the chunking is part of the key under which that state is reused. — checkpoints taken at chunk ends or semantic boundaries are reused without chunking in the key; the engine states no bitwise claim between a restored prefix and a fresh read
- splash [prompt-reading] prefill-runner: Where chunk boundaries change stored state, the chunking is part of the key under which that state is reused. — With bf16 recurrent state, chunk ends and capture points round the state, yet stored composite states are reused by a resumed request whose cold run would have rounded at other boundaries; the key does not include the chunking.

## Inventory errors

- strata prompt-builder.output_effect: recorded 'none'; source shows 'The opt-in effort_position puts a non-default reasoning effort in an injected system turn and the effort sentence of the first system message can be replaced (serve/server.py:270, 4745, 5745-5778); a shipped template replaces a missing pack template. The prompt changes, so not none.'
- strata engine-client.output_effect: recorded 'none'; source shows 'keys += top_k={tk if 1 <= tk <= 64 else 64} (serve/server.py:1659): a requested top_k of 0 or above 64 is sent as 64, changing sampled output.'
- strata dflash2-drafter.decisions: recorded 'Skip the draft round when the lookup match is at least this many tokens.'; source shows 'The skip is decided by the draft-policy rule skip_draft_for_lookup in include/strata/spec/window_rule.hpp, called from the host loop (src/program/generate.cpp:18893-18905, 20899-20913); it belongs to draft-policy.'
- strata http-front.decisions: recorded 'five admission and timeout decisions; nothing on who may call'; source shows 'An API key (Bearer or x-api-key), allowed host names and CORS origins gate /v1/* (serve/server.py:7605-7744, 9906-9911); the who-is-allowed decision is missing.'
- strata output-head.output_effect: recorded 'numeric (not established)'; source shows 'On the pack path the mixed activation is quantised to 8-bit q8_K before the vocabulary projection (src/core/layer.cpp:1425); that is a reduced activation precision, not last-bit rounding.'
- ds4 compressed-attention-state.output_effect: recorded "none (and decision 'Compressed rows optionally stored as F16')"; source shows 'ds4.c 17236-17246: on Apple the persistent compressed KV cache is stored in F16 by build (DS4_GPU_ATTN_COMP_CACHE_F16=1), F32 elsewhere, with F32 staging; storage width differs by platform, so the effect is numeric and the F16 choice is fixed per platform, not optional.'
- ds4 dense-attention-cache.output_effect: recorded 'none'; source shows "ds4.c 17248-17250: GLM's persistent compact cache is stored in F16 on all GPU backends while producers keep F32 staging; stored width is reduced, so the effect is numeric."
- ds4 disk-kv-checkpoint-store.output_effect: recorded 'numeric (reuse across quantizations brings state computed by another quantization)'; source shows 'ds4_kvstore.c 518-519, 616-643, 852-858: cross-quant reuse is accepted unless reject_different_quant is set; state computed under other routed-expert weights differs by more than last bits, so changes_output.'
- ds4 offline-converter-quantizer.when_things_go_wrong: recorded 'Merge script verifies shard sizes and checksums and keeps the previous default model (per docs)'; source shows 'gguf-tools/deepseek4-quantize.c 2042, 2793-2856 writes directly to the output path and exits on error leaving a partial file; deepseek41_quantize.py 248-314 and glm53_quantize.py 1113 write .partial (with a journal) and rename on completion. Shard checksum verification belongs to download_model.sh, listed outside the engine.'
- hyperqwen gptq-requantizer.decisions: recorded 'Width of the DFlash2 fc projection'; source shows 'The choice is the bit width of the fc projection (--fc-bits 4|8|16, default int4 GPTQ), not its dimension (drafter/quant_dflash2.py:5,9,29,59)'
- hyperqwen context-lookup-proposer.output_effect: recorded 'none'; source shows "Its own output_effect_when says greedy text may flip on near ties because block length changes rounding, which is the 'numeric' level of the inventory brief (patches/dflash2-lookup-drafting.patch, as cited)"
- ninfer draft-head-builder.output_effect: recorded 'none; changes only the acceptance rate'; source shows 'sampled acceptance draws depend on the proposals, so a different head changes the realised tokens under sampling (resampled) (include/ninfer/ops/speculative_accept.h 22-44)'
- ninfer mtp-drafter.output_effect: recorded 'none; changes only how many tokens are accepted per round'; source shows 'under sampling the accepted draft and the correction draw depend on the proposal (include/ninfer/ops/speculative_accept.h 22-44); greedy results follow the verify block shape'
- ninfer block-drafter.output_effect: recorded 'none; changes acceptance rate only'; source shows 'under sampling acceptance is min(1, p/q) and rejection resamples max(p-q,0), so the drawn tokens depend on q and the proposals (include/ninfer/ops/speculative_accept.h 60-67)'
- ninfer http-api.does: recorded 'no mention of caller authorisation'; source shows 'an optional API key is checked as a Bearer or x-api-key header on every route except /health and OPTIONS (src/serve/http_server.cpp 164-191, 358-365)'
- splash image-preparation.output_effect: recorded 'none'; source shows 'server/images.py:77,115 smart_resize resizes every image to a patch-aligned size within max_pixels, so the pixels the model sees are decided here (defines).'
- splash kv-spill-controller.output_effect: recorded 'none'; source shows "runtime/engine/Engine.hpp:145-158, 429, 641 the SSD cache's active-KV quota bounds a spilled request's output and ends it at that bound (changes_output)."

## Decisions not covered

- strata [draft-proposal] dflash2-drafter: skip the draft round when the lookup match is at least a given length
    missing (policy): whether the proposer is skipped when another source suffices (named only under draft-policy)
- strata [engine-supervision] engine-client: a top-k outside the engine's supported range is sent as the largest supported value
    missing (policy): how request settings outside what the engine supports are clamped or refused
- strata [expert-source] expert-source: the full set is filled from the published model files or from the engine's own repacked file
    missing (format): which stored copy or encoding of the selectively used weights the full set is filled from
- strata [memory-planning] startup-memory-sizing: with a per-layer profile the uniform slot count becomes a byte budget filled with slots of each layer's own block size
    missing (sizing): whether a cache's share is counted in uniform units or in bytes of blocks of different sizes
- strata [prefix-reuse] parked-conversations: host memory that must stay available after a park, a session save or a restore
    missing (threshold): memory that must stay free on the tier holding stored state after a store or restore
- strata [prefix-reuse] parked-conversations: an allocation is admitted only above a memory floor measured from system, control-group and operator figures; an unreadable figure refuses
    missing (policy): how the memory available to the store is measured, and when a store is refused for lack of it
- strata [prompt-preparation] prompt-builder: which tokenizer runs (the engine's own reimplementation built from the tokenizer files)
    missing (policy): which tokenizer implementation is used, and how it is held to the reference tokenizer's output
- strata [replica-routing] replica-router: whether several copies run at all
    missing (sizing): how many copies run
- strata [residency-policy] adaptive-tier: every use count is multiplied by a decay factor after each run
    missing (policy): how use counts age, so that recent use outweighs old use
- ds4 [draft-proposal] dspark-drafter: drafting disabled in quality and strict modes
    missing (policy): whether proposing is offered in modes that require output equal to non-speculative decoding
- ds4 [expert-source] prefill-layer-pagein: page-in mechanism: explicit read by default; advice, touching or read-ahead opt-in
    missing (policy): the mechanism by which the stored set is brought into readable memory ahead of use (explicit read, a hint to the operating system, touching a mapping)
- ds4 [modality-encoding] image-input-encoder: size limits on encoded bytes, dimensions and pixels
    missing (threshold): limits on the size and dimensions of media accepted for encoding
- ds4 [modality-encoding] image-input-encoder: remote URLs and file paths rejected
    missing (policy): which sources of media are accepted (inline data, remote fetch, local files)
- ds4 [model-edit] directional-steering: an active edit disables the shared-weight batched path
    missing (policy): whether an edited sequence may share a batched step with others, and what is done otherwise
- ds4 [model-partitioning] multi-gpu-placer: multi-GPU split refused together with weight streaming from storage
    missing (policy): which other engine features may be combined with splitting the model, and which are refused
- ds4 [output-interpretation] server-generation-loop: speculative decoding only when one session is served
    missing (policy): which generation features (speculation) are used when several requests are served together
- ds4 [prefix-reuse] disk-kv-checkpoint-store: store directory rescanned on every lookup, no kept index
    missing (policy): whether stored prefixes are found through a kept index or by scanning the store
- ds4 [prompt-preparation] tokenizer-and-chat-renderer: only the suffix after a reused prefix is tokenized
    missing (policy): whether the prompt is tokenized whole or in pieces joined at a reuse boundary
- ds4 [sampling] tool-call-sampling-mode: on a mode flip inside an accepted draft block, discard the rest and rewind to the boundary
    missing (policy): what is done with accepted proposed tokens when the per-position settings change inside them
- ds4 [sequence-lifecycle] session-timeline: state that cannot be truncated: a rewind outside the speculative window invalidates and forces reading again
    missing (policy): how a sequence is taken back to an earlier position: truncation, restoring a snapshot, or rebuilding from its tokens
- ds4 [sequence-lifecycle] session-timeline: per model: truncate, or restore one of a few snapshots, else replay
    missing (policy): how a sequence is taken back to an earlier position: truncation, restoring a snapshot, or rebuilding from its tokens
- hyperqwen [configuration] launch-profile-resolver: Which layers run int8 activations
    missing (policy): which settings that change output are on by default, and in which profile or deployment class
- hyperqwen [engine-supervision] stall-watchdog: No lock shared with the main loop
    missing (policy): whether the stall monitor shares any lock or resource with the loop it watches
- hyperqwen [modality-encoding] image-encoder: Bulk-copy per module rather than UVA zero-copy, which re-reads tiles over PCIe
    missing (placement): how encoder weights that are not resident are brought to the device: copied per use or read in place
- hyperqwen [modality-encoding] image-encoder: Pixel cap of 2048 image tokens and one image per prompt
    missing (threshold): limits on how much media one prompt may carry and how many embedding rows it may become
- hyperqwen [model-conversion] draft-vocab-builder: Number of rows kept
    missing (sizing): the size of a derived piece, such as how many vocabulary rows a shortlist keeps
- hyperqwen [model-conversion] chat-template-rewriter: Which effort names map to which template level; unknown ones fall through to no instruction
    missing (policy): how a derived template is corrected: which inputs it newly accepts and what each is mapped to
- hyperqwen [request-front] api-server: SSE keep-alive interval
    missing (timing): keep-alive for a response stream with nothing to send
- hyperqwen [sampling] sampler: Multi-block row softmax for up to 16 rows
    missing (policy): the kernel used for the sampling arithmetic and how it changes with the number of rows
- hyperqwen [state-tiering] kv-offload-tier: Retain the sliding-window history at the recurrent state's replay boundary under sparse retention
    missing (policy): which pieces of different kinds of state are kept together on the slower tier so that a restored state is usable
- ninfer [calibration] context-cost-calibrator: form of the fitted cost model for transfers and recompute
    missing (policy): the form of the model fitted to the measurements
- ninfer [draft-verification] state-commit: commit by graph replay or eager
    missing (policy): whether the commit runs from a recorded graph or is launched directly
- ninfer [expert-cache] expert-cache: bound on concurrently open uses
    missing (sizing): how many uses of cached blocks may be open at once
- ninfer [model-loading] shard-materializer: how reads are aligned and deduplicated when several destinations share a source
    missing (policy): how file reads are aligned and shared when several destinations need the same bytes
- ninfer [output-interpretation] output-interpreter: thinking budget
    missing (threshold): a budget on the reasoning part and what is done when it is reached
- ninfer [residency-policy] expert-residency-planner: balanced per-layer byte share for the fixed region, largest that leaves each window room
    missing (sizing): how cache capacity is divided between layers and between fixed and reusable regions
- ninfer [residency-policy] expert-residency-planner: two streaming windows first, one if two do not fit
    missing (sizing): how many streaming windows the reusable region holds, and the fallback when they do not fit
- ninfer [residency-policy] expert-residency-planner: CPU workers min(16, cores - 1) unless given
    missing (sizing): workers given to the second device that computes absent blocks
- ninfer [residency-policy] expert-residency-planner: upload slots at least 3, enough for two largest banks
    missing (sizing): number of upload slots sized from the largest blocks
- ninfer [state-pool] context-directory: logical references versus execution borrows
    missing (policy): whether holders that keep content and in-flight readers of its address are counted separately
- ninfer [state-tiering] context-transfer: chunk size and staging per slot
    missing (sizing): chunking and staging of copies between tiers
- ninfer [step-execution] rank-program: graph replay or eager per unit kind
    missing (policy): which kinds of step are replayed from a recorded graph and which are launched directly
- ninfer [step-scheduler] engine-control-loop: when to re-run admission (queue or capacity change, deadline)
    missing (timing): when waiting work is reconsidered for admission
- splash [calibration] ane-ffn-calibrator: remember a no-gain result too
    missing (policy): whether a negative result is recorded and reused like a positive one
- splash [configuration] device-probe: core count assumed when none is reported
    missing (failure): what is assumed when a fact about the machine cannot be read
- splash [device-backend] metal-command-backend: bound versus addressed buffer reach
    missing (placement): how the buffers a submission may touch are declared to the device
- splash [device-backend] metal-command-backend: per-encoder residency instead of queue residency
    missing (placement): at what granularity memory is made resident for submitted work
- splash [device-backend] metal-command-backend: heartbeat and keep-alive of the residency set
    missing (timing): how memory is kept resident for the device between submissions
- splash [engine-supervision] bootstrap-sequencer: warm up on reserved pages without allocating serving state
    missing (policy): where warmup gets its memory, and whether it may take memory serving will need
- splash [engine-supervision] native-loop: rerun memory control at the next command-free point
    missing (timing): where the process loop runs housekeeping between steps
- splash [engine-supervision] native-loop: flush newest restore points on clean stop within a budget
    missing (timing): what is saved on a clean stop, and within what time
- splash [memory-planning] streamed-parts-planner: replan with fewer streamed parts when that streams more
    missing (policy): how the set of large parts that stream instead of staying resident is chosen, and whether alternative sets are compared
- splash [modality-encoding] vision-encoder: per-image patch cap
    missing (threshold): the largest input the encoder accepts
- splash [model-conversion] model-installer: whether to include the vision tower
    missing (policy): which optional parts of the published model are included in what the engine is given
- splash [model-loading] model-inspection: which family a configuration describes
    missing (policy): how the model's architecture is recognised from its files and matched to what the kernels support
- splash [prompt-reading] prefill-runner: group or single chunk
    missing (policy): whether chunks of several sequences are read together, layer by layer
- splash [resource-governing] memory-ledger: claim rank among competing claims
    missing (precedence): the order in which competing claims for memory are served
- splash [sequence-lifecycle] lane-admission: which lane yields first
    missing (precedence): which running sequence gives way when resources run short
- splash [state-pool] kv-page-pool: KV format for the whole run
    missing (format): precision and layout of the state the pages hold
- splash [state-tiering] write-behind: pause while a claim waits for memory
    missing (timing): whether copying to the slower tier yields to work waiting for memory
- splash [state-tiering] kv-spill-controller: convert on refused growth
    missing (timing): what event moves a sequence's state to the slower tier

## Decisions covered loosely

- strata [configuration] run-config-generator: the expert cache size is left to the engine's automatic rule
    nearest: operator values, presets, measured values and defaults
- strata [configuration] launch-argument-resolver: a calibration record is applied only if model name, context length and image setting equal the configuration's
    nearest: operator values, presets, measured values and defaults
- strata [configuration] launch-argument-resolver: one drafter per run, and the drafter options rewritten to match it
    nearest: rules that derive a setting's default from other settings and machine facts
- strata [draft-policy] draft-policy: whether the window width is chosen step by step from each draft's probability and the measured cost of each width
    nearest: what it optimises
- strata [draft-policy] draft-policy: without the cost-aware window, the window ends before the first draft below a probability floor
    nearest: limits on the round
- strata [draft-proposal] mtp-drafter: rows the drafter's recorded graphs hold
    nearest: how many per round
- strata [draft-proposal] lookup-drafter: tokens a lookup may append after the neural drafts in the same window, and the shortest match it extends on
    nearest: how several sources are combined at each position
- strata [engine-supervision] engine-client: after a number of fatal device errors within a window the engine is not started again until the window passes
    nearest: restart, and what happens to requests in flight
- strata [expert-fetch] host-to-device-transfer: residency swaps copied one by one or as one batched copy
    nearest: how outstanding reads are ordered and joined
- strata [expert-source] expert-source: how long to wait for RAM an exiting program still holds before falling back
    nearest: what is used when the preferred place cannot hold the full set
- strata [expert-source] expert-source: a short arena still loads when a huge-page pool or free plus droppable file pages cover the need
    nearest: what is used when the preferred place cannot hold the full set
- strata [graph-capture] window-graphs: upper bound on the number of recorded batch layouts
    nearest: the memory recorded graphs may take
- strata [memory-planning] startup-memory-sizing: least working cache (slots for the smallest prompt chunk plus what a loan leaves)
    nearest: the order in which things are given up when memory is short, and when starting is refused
- strata [memory-planning] startup-memory-sizing: slots a loan to the prompt path leaves in the cache
    nearest: how the remainder is split between cache, state and concurrency
- strata [memory-planning] startup-memory-sizing: an automatic cache that cannot be allocated is retried at three quarters of its size
    nearest: the order in which things are given up when memory is short, and when starting is refused
- strata [memory-planning] host-memory-admission: the lookup table is locked in RAM only if RAM holds it plus the whole expert arena plus a headroom; unknown figures admit nothing
    nearest: what is priced before caches get the remainder
- strata [memory-planning] host-memory-admission: the engine may swap the arena for the file source on its own unless the operator chose RAM or named a shared arena
    nearest: an operator's explicit size against the computed one
- strata [memory-planning] host-memory-admission: page-locked memory held back while the arena registers and released right after
    nearest: the reserve left free
- strata [memory-planning] host-memory-admission: page-locked memory held until ready or until a guarded allocation is refused
    nearest: the reserve left free
- strata [memory-planning] host-memory-admission: a reserve that cannot be had is halved down to a floor, then skipped
    nearest: the order in which things are given up when memory is short, and when starting is refused
- strata [model-loading] model-file-reader: six metadata keys required; any other missing key keeps the compiled value
    nearest: what is done when a file is the wrong version, incomplete or of an unsupported shape
- strata [model-loading] model-file-reader: only expert count, experts per token and vocabulary size may differ from the compiled geometry
    nearest: what is done when a file is the wrong version, incomplete or of an unsupported shape
- strata [model-loading] expert-layout: native per-layer layout when its table file exists, else the canonical single-size layout
    nearest: which stored encoding of a tensor is loaded when the files carry more than one, and which kernels accept it
- strata [output-interpretation] request-runner: with thinking on and no budget, close the thinking early so the answer keeps a share of the limit
    nearest: how the generation is driven and continued for one request
- strata [output-interpretation] request-runner: non-finite logits before any token was sent: the same request is sent once more
    nearest: how the generation is driven and continued for one request
- strata [prefix-reuse] checkpoint-chain: a request may pin one restore point, which is then exempt from eviction
    nearest: what is evicted first
- strata [prompt-preparation] prompt-builder: tokens kept free between prompt plus output and the context length
    nearest: what happens when prompt plus output exceed the context
- strata [prompt-preparation] prompt-builder: an absent, zero or negative output limit means the rest of the context
    nearest: defaults against the request's settings
- strata [replica-routing] replica-router: hashes of fixed-size token blocks kept to track what each copy holds
    nearest: how a request is matched to a copy: least loaded, or the one holding reusable state
- strata [request-front] http-front: how often a watcher checks whether the client closed its socket
    nearest: what is done on disconnect, timeout or overload
- strata [residency-policy] adaptive-tier: an expert may enter only if its use count reaches a minimum
    nearest: the gain a change must bring, and a limit on changes per round
- strata [secondary-compute] cpu-expert-pool: the calling thread claims jobs itself during a batch
    nearest: number of workers
- strata [sequence-lifecycle] slot-scheduler: how often a request left alone in a slot returns to the solo path, and the fewest tokens it must still be allowed
    nearest: how a request is matched to a place: a slot or a lane
- strata [sequence-lifecycle] slot-scheduler: retries on another slot after a refusal, and how long a refused slot is kept out of the picks
    nearest: admission when resources are short
- strata [sequence-lifecycle] slot-scheduler: how long the control lines or a slot are held for a silent engine before it is ended
    nearest: how long a sequence may wait for resources before it fails
- strata [step-execution] window-loop: how long the host waits for a layer signal before one driver call to flush and check for a fault
    nearest: how long a layer may wait for something it needs
- strata [step-execution] session-loop: how long a late layer signal waits before one driver call
    nearest: how long a layer may wait for something it needs
- strata [step-scheduler] engine-command-loop: as many slot sessions as can be allocated; fewer than two turns batching off
    nearest: sequences and rows per step
- ds4 [calibration] expert-locality-profiler: set of simulated cache capacities
    nearest: what is measured and on which prompts
- ds4 [device-backend] gpu-backend: kernel per stored tensor format
    nearest: how a kernel variant is chosen per device and step shape (format is not named; it is under layer-compute)
- ds4 [device-backend] gpu-backend: prefill workspace shared between sessions in batch mode
    nearest: scratch and command buffers
- ds4 [draft-policy] dspark-scheduler: time-based judgement off by default, counts only
    nearest: what it optimises
- ds4 [draft-policy] dspark-scheduler: estimates reset at the start of each request
    nearest: how fresh the signals it decides from must be
- ds4 [draft-proposal] builtin-mtp-drafter: draft depth adapts from recent first-draft acceptance
    nearest: how many per round (adaptation is draft-policy's)
- ds4 [draft-verification] draft-verify-commit: after a correction, the corrected token is evaluated as an ordinary step
    nearest: commit at once or with the next step
- ds4 [expert-source] prefill-layer-pagein: only routed matrices are paged in when non-routed weights are already locked
    nearest: how much of the full set is made directly readable by a device, and which part first
- ds4 [memory-planning] memory-admission-guard: whether an explicitly raised OS wired limit overrides the budget heuristics
    nearest: an operator's explicit size against the computed one
- ds4 [model-conversion] offline-converter-quantizer: higher-precision routed experts in some layers (mixed recipe)
    nearest: precision per kind of weight (per kind, not per layer)
- ds4 [model-conversion] offline-converter-quantizer: padding a tensor's input width to a kernel-friendly size
    nearest: file layout, alignment and ordering of weights (padding changes a tensor's stored shape, not only its placement)
- ds4 [model-partitioning] multi-gpu-placer: greedy contiguous packing of layers in order within per-device budgets
    nearest: split by layers, by parts of each layer, or by selectively used weights
- ds4 [model-partitioning] multi-gpu-placer: expert split offered only for one family and an even device count
    nearest: split by layers, by parts of each layer, or by selectively used weights
- ds4 [model-partitioning] network-tensor-parallel: under speculation: leader drafts, verify is sharded, commit as full, prefix or rollback-replay
    nearest: how work outside the layers is divided between the parts
- ds4 [prompt-preparation] tokenizer-and-chat-renderer: old reasoning dropped from history except in tool context or after the last user message
    nearest: the template used and how it is corrected
- ds4 [request-front] http-api-server: no metrics, health or overload rejection
    nearest: what is done on disconnect, timeout or overload
- ds4 [residency-policy] expert-eviction-policy: use counts decay per decoded token, prefill does not age them, a new prefill resets them
    nearest: the replacement rule
- ds4 [residency-policy] expert-cache-preloader: preload not used for some families and off by default for one
    nearest: which ranking is used when no recorded ranking matches the model
- ds4 [resource-governing] power-throttle: smoothing of the measured work time the sleep is derived from
    nearest: the duty cycle allowed and the window it is averaged over
- ds4 [row-source] engram-row-reader: start row reads before the first layer, wait at the layer that uses them
    nearest: prefetching rows for coming or drafted tokens
- ds4 [row-source] engram-prewarm: number of warming threads and how often memory pressure is checked
    nearest: warming the table in the background and when to stop
- ds4 [sampling] token-sampler: default values of temperature, top-p and min-p
    nearest: default settings against the request's
- ds4 [sampling] token-sampler: candidate cap and skipping non-finite logits
    nearest: limits on candidates considered (handling of non-finite logits is not named)
- ds4 [sequence-lifecycle] slot-router: which slot is repurposed: empty, long idle, then shortest checkpoint; busy never
    nearest: admission when resources are short
- ds4 [session-persistence] session-payload-serializer: under tensor parallelism only tokens are restored and the prompt is read again
    nearest: in which configurations saving and restoring is offered
- hyperqwen [calibration] calibration-data-capture: Number of calibration rows
    nearest: time budget of a measurement run
- hyperqwen [configuration] launch-profile-resolver: Profile (batch or single-user) and context class (fast, long, huge)
    nearest: rules that derive a setting's default from other settings and machine facts
- hyperqwen [configuration] launch-profile-resolver: Drafter kind and number of draft tokens
    nearest: rules that derive a setting's default from other settings and machine facts
- hyperqwen [configuration] launch-profile-resolver: Pin the pool by bytes or by utilisation; skip the pin under tensor parallelism
    nearest: whether an operator value is a hard limit or a target
- hyperqwen [configuration] launch-profile-resolver: Prefix caching on with align-mode Mamba state, and the snapshot retention interval
    nearest: rules that derive a setting's default from other settings and machine facts
- hyperqwen [configuration] correctness-pins: Which combinations are pinned and to what
    nearest: which combinations are refused
- hyperqwen [configuration] correctness-pins: Whether an explicit operator override is honoured
    nearest: operator values, presets, measured values and defaults
- hyperqwen [draft-policy] drafter-free-chains: Single request only; greedy only by default (point mass under sampling displaced better drafts, -8 percent)
    nearest: decisions per sequence or jointly across sequences sharing a step
- hyperqwen [draft-policy] verify-length-controller: Two qualifying steps to enter, STICKY steps to leave (single request only)
    nearest: when drafting pauses and resumes
- hyperqwen [draft-policy] verify-length-controller: Take the long block unconditionally below a context length (off by default)
    nearest: limits on the round
- hyperqwen [draft-proposal] mtp-drafter: Draft from the target's top-k/top-p support; optional draft temperature scale
    nearest: the set of tokens proposals are restricted to / greedy or sampled proposals
- hyperqwen [draft-proposal] dflash2-drafter: Draft block equals the trained block even when the verify block is longer (the grouped convolution resets on block boundaries)
    nearest: how many per round
- hyperqwen [graph-capture] graph-capture: FULL, PIECEWISE or FULL_AND_PIECEWISE per profile
    nearest: where a graph must be split so that host work can run between its parts
- hyperqwen [layer-compute] full-attention-compute: Sparse attention budget when LSA is on
    nearest: any deliberate change to the model's arithmetic (it changes output and needs permission)
- hyperqwen [memory-planning] memory-budget-planner: Measure after an uncounted warm profile pass, and empty the allocator cache before allocating the pool
    nearest: whether a figure is measured by a trial run or computed
- hyperqwen [memory-planning] memory-budget-planner: Measure graph memory by allocator reserved bytes, not the driver's free-memory delta
    nearest: whether a figure is measured by a trial run or computed
- hyperqwen [modality-encoding] image-encoder: Load the tower at all (default: language-model only)
    nearest: whether encoder weights stay resident
- hyperqwen [model-conversion] model-dir-publisher: Order of writes: shards, then config.json, then the index last as the commit point
    nearest: whether conversion is one step or resumable stages / what happens to a conversion that is interrupted
- hyperqwen [model-conversion] model-dir-publisher: Whether a checkpoint is an extendable compressed-tensors pack-quantized schema, checked before any read
    nearest: what happens to a conversion that does not match its source
- hyperqwen [model-conversion] draft-vocab-builder: Which extra scripts (CJK, Cyrillic) are appended and under what row budget
    nearest: the data a derived piece is selected or fitted from, and what is eligible for it
- hyperqwen [output-constraint] grammar-constraint: Hold every tool to its schema, not only strict ones
    nearest: which rules are offered
- hyperqwen [positional-state-store] attention-kv-store: Padded-page views when another group's promoted page is larger
    nearest: precision and layout of stored state
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Draft passes after the first only allocate slots, never flush
    nearest: when state held in a staging precision is converted to its stored format
- hyperqwen [prefix-reuse] prefix-cache: Hash unit (128 on KVarN)
    nearest: the key that decides whether stored state may be reused
- hyperqwen [recurrent-state-store] recurrent-state-store: Copy state across a block boundary during chunked prefill only when the column changes
    nearest: when a snapshot is taken
- hyperqwen [request-front] access-guard: Bind to loopback when no key is set (outside containers)
    nearest: who is allowed and how
- hyperqwen [sampling] sampler: Use one topk instead of a full-vocabulary sort when every request's top-k is at most 64 (known on host, no sync)
    nearest: limits on candidates considered
- hyperqwen [state-pool] pool-layout-planner: Charge recurrent-state pages for every in-flight async batch, plus speculative scratch and prefill checkpoints
    nearest: page size and how the pool is split between kinds of state
- hyperqwen [state-tiering] kv-offload-tier: Which groups count as draft attention (only the drafter's sliding-window groups)
    nearest: which kinds of state the slower tier holds
- hyperqwen [step-execution] model-runner: Truncate the draft tokens handed for verification to the controller's count
    nearest: sequences and rows per step
- hyperqwen [step-scheduler] request-scheduler: Admission count (max-num-seqs) versus residency (pages)
    nearest: sequences and rows per step
- hyperqwen [step-scheduler] request-scheduler: Preempt and recompute when the pool is full
    nearest: which sequence is paused when resources run short
- ninfer [device-backend] executor: number of compute and context frames
    nearest: scratch and command buffers
- ninfer [device-communication] collective-communication: policy override (native, NCCL, automatic)
    nearest: the transport
- ninfer [engine-supervision] rank-launcher: message encoding by fields only; no cross-version compatibility
    nearest: the transport between the serving side and the engine
- ninfer [expert-dispatch] hybrid-moe-dispatch: GPU subset versus CPU complement per layer from a snapshot of ready experts
    nearest: the share of misses fetched now against left to another device
- ninfer [graph-capture] execution-graphs: context-length buckets for child graphs
    nearest: which step shapes are recorded ahead and which on first use
- ninfer [layer-compute] layer-compute: KV encoding
    nearest: kernel variant per device class, step shape and stored-state format
- ninfer [memory-planning] startup-memory-planner: bounded correction of automatic capacity after an over-budget preparation; explicit capacity kept
    nearest: the order in which things are given up when memory is short, and when starting is refused
- ninfer [modality-encoding] vision-encoder: which complete units fit the window in one execution
    nearest: memory window for the encoder
- ninfer [model-conversion] checkpoint-converter: which architecture constants must match before a recipe applies
    nearest: what happens to a conversion that is interrupted or does not match its source
- ninfer [model-loading] shard-materializer: whether a slice can be expressed value-preservingly, else the format rejects it
    nearest: whether weights are re-encoded at load and how
- ninfer [model-partitioning] partition-planner: where the PLE table lives (device shards on two machines, disk otherwise)
    nearest: which devices may hold a part of the model
- ninfer [output-constraint] grammar-constraint: which constraint languages compose for a request
    nearest: which rules are offered
- ninfer [output-interpretation] output-interpreter: reasoning and tool formats per model family
    nearest: how tool calls are parsed, repaired or retried
- ninfer [prefix-reuse] context-resource-manager: retention value only from real cross-request adoption
    nearest: what is evicted first
- ninfer [prefix-reuse] context-resource-manager: attention-owner rank: balanced load first, then longest local prefix
    nearest: which device restored state is placed on
- ninfer [prompt-preparation] prompt-preparer: where restore points may sit (not inside media)
    nearest: keeping the start of the prompt stable so that stored state can be reused
- ninfer [request-front] responses-store: record and byte limits of stored responses
    nearest: whether earlier responses are stored for later requests to refer to
- ninfer [row-source] ple-row-source: disk path or device-shard path by deployment
    nearest: the table on storage, mapped, or locked in memory
- ninfer [sequence-lifecycle] model-session: full permit before verify that covers the later commit peak
    nearest: a sequence's state allocated up front or grown on demand
- ninfer [step-execution] rank-program: where host handoffs split device work (grammar mask, CPU experts, final acceptance)
    nearest: cutting a step into parts so that work on two devices overlaps
- ninfer [step-scheduler] engine-control-loop: order within a cycle: control span, then decode, then one prefill chunk
    nearest: how a long prompt yields to generation in progress
- ninfer [step-scheduler] request-scheduler: service quantum 1 s, up to 4 s when restore work was expensive
    nearest: order and fairness between sequences
- splash [calibration] ane-ffn-calibrator: noise tolerance for the least chunk rows
    nearest: the rule that accepts or rejects a measured result
- splash [configuration] device-probe: which GPU class a family number maps to
    nearest: which settings are fixed per machine class
- splash [device-backend] metal-command-backend: spin the GPU through short host steps or not
    nearest: where a step is split so host work can run inside it
- splash [draft-proposal] draft-state: cache the window, not the ring
    nearest: where the proposer's own state is kept
- splash [draft-proposal] draft-state: rebuild the ring in the next prefill chunk after a restore
    nearest: how the proposer's state is built while the prompt is read
- splash [draft-verification] acceptance-commit: emit a stop or last budgeted token without a target cycle
    nearest: who may shorten the accepted prefix afterwards (stop conditions, limits)
- splash [engine-supervision] engine-supervisor: which failures are permanent or memory-caused
    nearest: whether a failed start is retried with a reduced configuration
- splash [engine-supervision] engine-supervisor: restart backoff base and cap
    nearest: restart, and what happens to requests in flight
- splash [engine-supervision] native-loop: bound the input queue to one largest frame
    nearest: the transport between the serving side and the engine
- splash [expert-cache] expert-store: which size's chunk to release or regrow
    nearest: total size and whether it can grow or shrink while running
- splash [expert-cache] expert-store: release one chunk, or all to floor under critical pressure
    nearest: total size and whether it can grow or shrink while running
- splash [expert-fetch] expert-read-ahead: read-ahead piece size
    nearest: staging area and how many fetches at once
- splash [memory-planning] streamed-parts-planner: expert floor share depending on whether KV can spill
    nearest: how the remainder is split between cache, state and concurrency
- splash [memory-planning] memory-plan: what bounds the context length
    nearest: how the remainder is split between cache, state and concurrency
- splash [modality-encoding] vision-encoder: build the arena only when an image waits
    nearest: memory window for the encoder
- splash [modality-encoding] image-embedding-cache: least recently used first
    nearest: caching of encoded media and its key
- splash [modality-encoding] image-embedding-cache: held entries form the floor
    nearest: caching of encoded media and its key
- splash [model-conversion] model-installer: pairing of a separately trained draft with a target family
    nearest: which derived pieces are built (draft head, shortlist vocabulary, extra copies)
- splash [model-loading] weight-layout-planner: which parts are left out of the image to stream
    nearest: what is loaded at start and what on first use
- splash [prefix-reuse] prefix-block-cache: resident blocks form a root subtree
    nearest: what is evicted first
- splash [prefix-reuse] composite-state-cache: retire rolling checkpoints once a newer one is published
    nearest: what is evicted first
- splash [prompt-preparation] prompt-builder: reuse cached tokens only where the tokenizer provably splits
    nearest: caches of rendered or tokenized prompts
- splash [prompt-reading] prefill-runner: number of layer passes
    nearest: how it shares the device with generation in progress
- splash [resource-governing] weight-residency: restore one part per tick
    nearest: releasing large holdings when idle and restoring them
- splash [resource-governing] weight-residency: abandon a restore when no request waits and memory is refused
    nearest: who may wait for memory and who is refused
- splash [resource-governing] memory-governor: pool growth admitted on its net change when cache funds it
    nearest: when holders that gave memory back may grow again
- splash [resource-governing] memory-ledger: take rights per claim class, timing and priority
    nearest: the order in which holders give up memory
- splash [scoring] option-scoring: which options have single-token slots
    nearest: limits on what can be scored
- splash [secondary-compute] ane-ffn-split: which program size a chunk uses
    nearest: how work is cut into jobs
- splash [secondary-compute] ane-ffn-split: stop it when a window of commands shows no gain
    nearest: when a share is too small or too large to hand over
- splash [sequence-lifecycle] lane-admission: rank for memory
    nearest: admission when resources are short
- splash [sequence-lifecycle] lane-admission: projected output tokens for admission
    nearest: admission when resources are short
- splash [state-pool] kv-page-pool: extent size target
    nearest: page geometry shared by kinds of state of different sizes
- splash [state-tiering] ssd-cache-tier: share of writes in flight per kind
    nearest: the tier's size and write budget
- splash [state-tiering] ssd-cache-tier: drop states not in use while the write budget is spent
    nearest: what is done when the tier is full or a read fails
- splash [state-tiering] kv-spill-controller: which requests spill at admission
    nearest: what leaves first
- splash [state-tiering] spilled-kv-reader: one or two staging buffers to overlap reads with attention
    nearest: copying ahead of need
- splash [step-scheduler] request-scheduler: group commands run in layer passes
    nearest: sequences and rows per step
- splash [telemetry] telemetry: a status read never moves admission
    nearest: what is recorded by default and what on request

