# Node types draft 0.5: independent checks, round5

44 types, 496 choices. Thresholds were fixed on 2026-11-16 in `validation/criteria.yaml`, before this draft was written.

| Check | Result | Threshold | |
|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 236/240 = 98% | at least 90% | pass |
| Decisions plainly covered by a choice | 647/715 = 90% | at least 80% | pass |
| Decisions covered only loosely | 64/715 = 9% |  |  |
| Decisions not covered | 4/715 = 1% | at most 5% | pass |
| Claims an engine contradicts | 17 | at most 0 | FAIL |
| Parts assigned to the wrong type in the reference | 2 |  |  |

## Per engine

| | strata | ds4 | hyperqwen | ninfer | splash |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 247 | 115 | 115 | 104 | 134 |
| Plainly covered | 94% | 90% | 89% | 94% | 84% |
| Not covered | 0% | 0% | 2% | 0% | 1% |
| Contradicted claims | 3 | 5 | 1 | 3 | 5 |
| Relaxed `should` rules not yet noted | 0 | 0 | 0 | 1 | 0 |
| Inventory entries the source corrects | 2 | 2 | 0 | 2 | 2 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 225 | 15 | 0 |
| rater-b | 206 | 34 | 0 |

## Disagreements on type

- hyperqwen/pool-layout-planner: reference state-pool; rater-a memory-planning, rater-b state-pool — rater-b: It is a startup layout and admission-capacity computation, not run-time page handout.
- strata/engine-command-loop: reference sequence-lifecycle or step-scheduler; rater-a engine-supervision, rater-b engine-supervision — rater-a: Advancing every active slot one window between commands and serialising prompt reads is a step-composition decision, not only running the loop. | rater-b: It is the engine-side command loop advancing slots a window at a time, which is not supervision of start and failure.
- ninfer/expert-priority-table: reference calibration; rater-a calibration, rater-b residency-policy
- hyperqwen/drafter-free-chains: reference draft-policy; rater-a draft-policy, rater-b draft-proposal — rater-b: It also decides to skip the drafter's forward while a lookup chain holds.

## Wrong assignments

- ninfer state-commit: draft-verification -> draft-verification, also recurrent-state-store. It owns the transition records from which GDN/KDA recurrent state is replayed from the unchanged start state, which is the recurrent-state-store form 'a commit deferred until acceptance is known'; no ninfer part is assigned recurrent-state-store although the models have large fixed-size recurrent state.
- ninfer context-pool: state-pool -> state-pool, also positional-state-store. It holds every request's paged KV planes in the stored encoding, and no other ninfer part is assigned positional-state-store although the engine plainly keeps per-position attention state. The primary type is right; the second job is unassigned.

## Contradicted claims

- strata [memory-planning] startup-memory-sizing: effect_on_output: rounding when what it places where decides which device computes something
    evidence: Its last-resort ladder gives the prompt path its own buffers at 1024, 512 or 256 tokens, which sets the prompt chunk; docs/RESEARCH_RUNS.md:60 says a change of chunking changes the rounding and docs/MESSAGE_BOUNDARY_CACHE.md:65 that chunk geometry can change floating-point results. No listed case covers a size that changes how the computation is cut.
    fix: rounding when what it places where decides which device computes something, or a size it sets (such as the prompt chunk) changes how the computation is cut
- strata [prefix-reuse] checkpoint-chain: effect_on_output: rounding when the stored state was produced under other rounding than a fresh read: reduced width, other chunk boundaries, another batch path, or computation placed on other devices
    evidence: The inventory records numeric when a checkpoint cut ends a prompt part and so changes the chunking of the prompt read; that changes the output of the request that stores the checkpoint, with no reuse involved. The listed cases cover only the effect of reusing a state.
    fix: add: rounding when where it places a restore point splits the prompt read and so changes the chunking of the request that stores it
- strata [step-execution] window-loop: effect_on_output: exact when one sequence per step, or kernels that treat each row independently
    evidence: With one sequence the width of the verify window changes a row's arithmetic: draft-verifier records numeric for a greedy request with a native IQ pack and experts on the CPU, because the grouped CPU kernels round differently by window width; mtp-drafter and lookup-drafter record that the number of drafts sets that width. One sequence per step is not enough for exact.
    fix: exact when every row's arithmetic is independent of how many rows the step holds; rounding when sequences sharing a step, or the number of rows of one sequence's step, change the arithmetic of a row
- ds4 [device-backend] gpu-backend: effect_on_output: exact when one variant per operation; rounding when the variant chosen depends on device class, step shape or batch width
    evidence: ds4_cuda.cu 1236-1277: on a single CUDA GPU the default kernel tier for steps of 2 or more rows (prefill and batched verify) quantises activations to Q8_1 before the matmul; 14787-14792: the indexer runs in MXFP4 for steps of 32 or more tokens. Both are off with --quality (DS4_CUDA_MMQ=0 for the first). The backend's own variant choice by step width thus reduces activation precision, which none of its cases covers.
    fix: add: approximate when the variant it chooses for a device or step width computes activations at reduced precision; such a variant is on only explicitly or as a recorded default that can be turned off
- ds4 [draft-verification] draft-verify-commit: effect_on_output: approximate when ... the checked block runs at a reduced activation precision that the weights permit
    evidence: Batched verify (2 or more rows) on CUDA goes through the same Q8_1 activation tier by default (ds4_cuda.cu 1236-1250, 'prefill and batched verify'); the weights carry no such permit, so the case's condition misses this engine's cause.
    fix: approximate when ... the checked block runs at a reduced activation precision selected by its width, whether the weights or the kernel tier permit it
- ds4 [layer-compute] routed-expert-ffn: must: Unless an approximation is in effect that was turned on at conversion or at run time, explicitly or as a recorded default, the sequence of layers and operations the model defines is kept. (effect approximate: where the weights carry a permit for it, this can depend on how many rows a step holds)
    evidence: ds4_cuda.cu 1236-1277: Q8_1 activation quantisation for routed IQ2_XXS/Q2_K and dense Q8_0 GEMMs at 2 or more rows is on by default; nothing records it with the run's settings (a message is printed only when it is turned off), and the weights carry no permit for it; the kernel tier, not the weights, decides it by row count.
    fix: Unless an approximation is in effect that was turned on explicitly or as a default that can be turned off, ...; a reduced activation precision may depend on how many rows a step holds, whether permitted by the weights or chosen by the kernel tier, and is stated with the run's settings
- ds4 [model-partitioning] pipeline-parallel: effect_on_output: approximate when activations cross between devices at reduced precision (and rounding only when partial results are combined)
    evidence: Correction (round4): f16 on the wire is numeric only (another floating-point width); only the 8-bit FP8 E4M3 wire format changes output. The type has no rounding case for a narrower float on the wire, so it files f16 as approximate.
    fix: rounding when partial results are combined across devices or activations cross at another floating-point width; approximate when activations cross quantised (8-bit or lower)
- ds4 [prompt-reading] prompt-prefill-driver: must: ... the state it leaves is the state of that prompt up to rounding, or up to the reduced activation precision the weights permit for wide chunks, whatever the chunking.
    evidence: On CUDA the default prefill tier quantises activations to Q8_1 for any chunk of 2 or more tokens (ds4_cuda.cu 1236-1277); this precision is not one the weights permit or record, and it is not an explicitly turned-on approximate path.
    fix: ... up to rounding, or up to a reduced activation precision for wide chunks that the weights permit or the run's settings state, whatever the chunking
- hyperqwen [draft-verification] draft-acceptance: effect exact when 'greedy decoding with exact agreement, or sampling where each position's draw is keyed independently of the proposal...'
    evidence: The inventory records that greedy output under speculation depends on block length, batch and cache state through rounding (draft-acceptance output_effect_when; surprises); the checked block always runs on the split-KV verify path, not single-token decoding, so greedy with exact agreement is not bit-exact here.
    fix: exact when greedy decoding with exact agreement and the checked block is computed by the same kernels and accumulation order as single-token decoding; otherwise rounding
- ninfer [model-conversion] checkpoint-converter: effect_on_output: exact when it only re-arranges bytes ...; approximate when it changes the precision or vocabulary of what the full model computes
    evidence: Importing an already-encoded NVFP4 checkpoint keeps the codes but rounds 1/multiplier to an FP32 divisor (inventory output_effect_when). That is a last-bit change of values against the imported source, neither a pure re-arrangement nor a change of precision; no listed case covers it.
    fix: Add: rounding, when it re-expresses stored scales or other values in another floating-point form without changing the stored precision.
- ninfer [prefix-reuse] context-resource-manager: effect_on_output: rounding when the stored state was produced under other rounding than a fresh read: reduced width, other chunk boundaries, another batch path, or computation placed on other devices
    evidence: Activation precision of AllowA4 projections depends on the step's token count (corrections for layer-compute, chunked-prefill, request-scheduler). A checkpoint captured from decode or verify rows (16-bit activations) or from a different chunking differs in precision, not last bits, from a fresh chunked read (4-bit activations), and choosing restore over recompute is this node's own choice.
    fix: Add: approximate, when the stored state was produced at another activation precision than a fresh read would use, because the precision follows the width of the step that produced it.
- ninfer [scoring] causal-scorer: A score is computed by the same model and arithmetic as generation.
    evidence: Scoring reads the given sequence in prefill-width chunks; generation produces a token's logits in decode or verify rounds of few rows. With AllowA4 permits the activation precision follows the row count (corrections for layer-compute and chunked-prefill), so the arithmetic of a scored position differs in precision from the arithmetic that generated it.
    fix: A score is computed by the same model, weights and kernels as generation; where precision depends on the width of a step, the width the score was computed at is stated.
- splash [media-preparation] document-renderer: effect_on_output: defines, when how media is resized or cut decides the model's input
    evidence: Correction (round4): server/documents.py:133-153 extracts page text as well as rendering pages at a chosen scale; text extraction is neither resizing nor cutting.
    fix: defines, when how media is converted (text extracted, pages rendered), resized or cut decides the model's input.
- splash [model-loading] weight-image-loader: effect_on_output cases: exact when weights are used as stored or re-encoded without changing their values; resampled when it reduces weights used only for proposals under sampling
    evidence: It quantizes the BF16 draft to 4 bits at load; under greedy decoding this leaves the target's output unchanged, a case none of the listed conditions covers (model-conversion lists it, model-loading does not).
    fix: exact: weights are used as stored, re-encoded without changing their values, or reduced only for proposals under greedy decoding.
- splash [output-constraint] thinking-budget: effect_on_output: defines, when: always, by design
    evidence: Output changes only whenever the budget runs out before the model ends thinking (inventory output_effect_when); below the budget the output is that of the unconstrained model.
    fix: defines, when the rule forbids or forces a token the model would otherwise have produced; exact otherwise.
- splash [prompt-reading] prefill-runner: Unless an approximate path that was explicitly turned on is taken, the state it leaves is the state of that prompt up to rounding ... whatever the chunking.
    evidence: The W8A8 Neural Engine share of dense FFN prefill (ane-ffn-split, inventory changes_output) is on by default; server/serve_options.py:755-766 offers only --disable-ane, default False. The approximate path is taken without being explicitly turned on.
    fix: Unless an approximate path is in effect that was turned on explicitly or as a recorded default that can be turned off, the state it leaves is the state of that prompt up to rounding, whatever the chunking.
- splash [resource-governing] memory-governor: A soft figure is exceeded only on the operator's explicit choice and with a warning.
    evidence: The host margin is a soft figure the engine sets itself; floor work always passes the host rule and in-service work passes as an exempt claim once nothing in place meets it (runtime/engine/MemoryGovernor.hpp:294-305), with no operator choice.
    fix: A soft figure is exceeded only by classes of work the engine states in advance, or on the operator's explicit choice.

## Relaxations

- ninfer [calibration] expert-priority-table: A recorded result is used only where its validity key matches the model, machine and build. — The compiled-in ranking applies whenever the architecture geometry (hidden size, layers, experts, top-k) matches; any other model or fine-tune of the same shape receives it, and the machine and build are not part of the key. The type's relaxed text names missing driver versions or no key, not a key of shape only.

## Inventory errors

- strata startup-memory-sizing.output_effect_when: recorded 'bit_exact when the sizing only moves where bytes are read from (output head on host, smaller prompt chunks); inferred'; source shows 'A smaller prompt chunk changes the chunking and with it the rounding (docs/RESEARCH_RUNS.md:60, docs/MESSAGE_BOUNDARY_CACHE.md:65). Smaller chunks are numeric, not bit_exact.'
- strata host-memory-admission.output_effect: recorded 'none; bit_exact for arena or file source, per the startup message, not verified'; source shows "A missed expert is fetched to the GPU only when its source bytes are page-locked (src/core/expert_source.cpp:5056-5063, d.src->pinned); otherwise it stays with the CPU. Choosing the file source instead of the registered arena moves uncached experts from GPU to CPU computation, which the inventory's expert-source entry records as numeric. The choice is numeric, not none."
- ds4 gpu-backend.output_effect: recorded 'numeric (scalar, batched and tensor-parallel kernels are not numerically identical)'; source shows 'ds4_cuda.cu 1236-1277: single-GPU CUDA uses the vendored mmq tier by default for steps of 2 or more rows, quantising activations to Q8_1 (off with --quality, DS4_CUDA_MMQ=0 or several GPUs); ds4_cuda.cu 14787-14792: MXFP4 indexer for steps of 32 or more tokens with 1024 or more compressed rows (off with --quality). Reduced activation precision is changes_output, on by default, settable off.'
- ds4 prompt-prefill-driver.output_effect: recorded 'numeric (batched prefill versus token-by-token decode differ in summation order)'; source shows 'Same source as above: on CUDA, prefill chunks of 2 or more tokens run with Q8_1-quantised activations by default (ds4_cuda.cu 1236-1277), so prefill versus decode differs beyond summation order unless --quality is set.'
- ninfer context-resource-manager.output_effect: recorded 'numeric; a restored prefix was read with different chunk boundaries than a fresh read'; source shows "Activation precision of AllowA4 projections follows the step's token count (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 23-39; tools/convert/official_recipes.py AllowA4 permits; src/models/common/bindings.cpp 43-55), so state captured at another step width differs in precision; the level is changes_output, as already corrected for chunked-prefill."
- ninfer media-preparer.output_effect: recorded 'none'; source shows "It selects which source frames of a video are used and permits a truncated tail after a minimum frame count, and resizes and orders patches by the processing plan (src/media/decode/decode.h 30-37, 77-91; src/product/media_acquire/acquire.h), so it decides the model's input: changes_output."
- splash ane-ffn-split.output_effect_when: recorded 'when the split runs (27B prefill with --ane on and a calibrated gain)'; source shows 'The split is on by default for dense models; the server offers only --disable-ane (default False), which passes --ane off to the engine (server/serve_options.py:755-766).'
- splash draft-proposer.output_effect: recorded 'none (while output_effect_when says sampled lanes see different tokens)'; source shows "Sampled acceptance u*q < p uses the draft's probabilities (runtime/metal/kernels/decode/sampling.metal:1460-1510, recorded under acceptance-commit as changes_output), so under sampling the proposal changes the draw: changes_output for sampled lanes."

## Decisions not covered

- hyperqwen [draft-policy] verify-length-controller: take the long block unconditionally below a context length
    missing (threshold): a context length below which the larger round width is taken regardless of the other signals
- hyperqwen [draft-verification] draft-acceptance: acceptance kernels must not specialise on batch size
    missing (policy): which step dimensions the acceptance kernels may be compiled or specialised on
- splash [resource-governing] memory-governor: pool growth admitted on its net change when cache funds it
    missing (policy): whether a holder's growth that displaces reclaimable cache is charged at its net change or at its full size
- splash [step-scheduler] request-scheduler: group commands run in layer passes
    missing (policy): whether prompt chunks of several sequences are grouped into one step that runs layer by layer

## Decisions covered loosely

- strata [configuration] run-config-generator: the speculative window and confidence floor written by default
    nearest: rules that derive a setting's default from other settings and machine facts
- strata [configuration] run-config-generator: an option differing from what setup last wrote counts as the person's and is kept, except options setup re-decides
    nearest: operator values, presets, measured values and defaults
- strata [configuration] launch-argument-resolver: one drafter is chosen per run and the drafter options are rewritten to match
    nearest: how a known-bad combination is handled: refused, or one member replaced
- strata [draft-proposal] lookup-drafter: most recent end positions kept per trigram
    nearest: how a lookup source matches earlier text, and how far back it searches
- strata [draft-verification] draft-verifier: the exact gated rule runs only in a stated set of configurations; elsewhere an older rule runs with a warning that its distribution is off
    nearest: the acceptance rule under sampling
- strata [draft-verification] draft-verifier: the commit graph is launched without waiting; every reader elsewhere waits for it first
    nearest: commit at once or with the next step
- strata [expert-dispatch] expert-dispatch: the conditions under which omitting low-ranked misses is on by default (share of blocks already cached, block format), stated at start (added by the correction)
    nearest: whether low-ranked selections may be omitted
- strata [layer-compute] layer-kernels: order of operations within a layer, including where routing is published to the host and where the shared expert and the combine run
    nearest: how independent operations are ordered to overlap with work on another device
- strata [layer-compute] layer-kernels: order of operations within an attention mixer, including appending to the stores and making selected blocks resident before attention
    nearest: how independent operations are ordered to overlap with work on another device
- strata [memory-planning] startup-memory-sizing: lowest value the reserve is lowered to so that the minimum cache fits
    nearest: the order in which things are given up when memory is short, and when starting is refused
- strata [memory-planning] host-memory-admission: the engine may replace the arena by the file source on its own unless the operator fixed RAM reads by hand, named a shared arena or disabled the fallback
    nearest: an operator's explicit size against the computed one
- strata [model-loading] expert-layout: native per-layer layout table when its file exists, else the canonical layout with one blob size
    nearest: which stored encoding of a tensor is loaded when the files carry more than one, and which kernels accept it
- strata [prefix-reuse] parked-conversations: the host memory the store may take: given, or computed once at start as a share of available memory with a cap and a floor
    nearest: how many are kept and where
- strata [row-source] ngram-reader: in direct mode, a periodic read of one random page keeps storage awake until a time after the last request
    nearest: warming the table in the background and when to stop
- strata [sequence-lifecycle] slot-scheduler: how often a prompt read in progress gives way to a waiting request whose prompt is at most half as long
    nearest: the order in which waiting prompts are read, and whether several are read together
- strata [step-execution] window-loop: per window: the graph variant in which the device plans each layer alone when every block of the stage is resident, else the variant in which the host serves each layer
    nearest: one step as a whole, or driven layer by layer
- ds4 [device-backend] gpu-backend: Prefill workspace shared between sessions in server batch mode
    nearest: scratch and command buffers
- ds4 [expert-cache] routed-expert-cache: Metal: cache buffers locked in memory; lock failure lowers the effective limit
    nearest: what is done when the cache cannot be allocated at its planned size
- ds4 [memory-planning] memory-admission-guard: Whether an explicitly raised OS wired limit overrides the budget heuristics
    nearest: an operator's explicit size against the computed one
- ds4 [memory-planning] ssd-cache-planner: Default share of the working set and the range an operator override is clamped to
    nearest: the reserve left free
- ds4 [positional-state-store] dense-attention-cache: Full dense cache with a length cap versus compact latent cache
    nearest: precision and layout of stored state
- ds4 [prefix-reuse] slot-router: Ordered tiers of match kinds (visible transcript, tool-output bindings, rewind, token prefix, rendered-text prefix)
    nearest: which store is used when several hold a match
- ds4 [prefix-reuse] slot-router: Continuations pinned to their slot
    nearest: whether a request may pin stored state against eviction
- ds4 [residency-policy] expert-eviction-policy: Heat increments on every selection, misses included, not only hits
    nearest: the replacement rule
- ds4 [row-source] engram-prewarm: Warm only when model, runtime, table and a reserve fit physical memory
    nearest: warming the table in the background and when to stop
- ds4 [row-source] ngram-row-reader: Prefetch only for chunks above a minimum size and within a buffer cap
    nearest: prefetching rows for coming or drafted tokens
- ds4 [sampling] tool-call-sampling-mode: Which tag sets count as structure
    nearest: whether settings change per position, for example greedy on structure and sampled on content
- ds4 [session-persistence] session-payload-serializer: Under tensor parallelism, load only tokens and re-prefill
    nearest: in which configurations saving and restoring is offered
- hyperqwen [configuration] launch-profile-resolver: drafter kind and number of draft tokens
    nearest: named profiles and what each fixes
- hyperqwen [configuration] launch-profile-resolver: pin the pool by bytes or by utilisation; skip the pin under tensor parallelism
    nearest: whether an operator value is a hard limit or a target
- hyperqwen [configuration] launch-profile-resolver: prefix caching on with align-mode recurrent state, and the snapshot retention interval
    nearest: which settings that change output are on by default, and in which profile
- hyperqwen [configuration] correctness-pins: whether an explicit operator override of a pin is honoured
    nearest: precedence: operator values, presets, measured values and defaults
- hyperqwen [draft-proposal] mtp-drafter: draft from the target's top-k/top-p support; optional draft temperature scale
    nearest: the set of tokens proposals are restricted to (covers the support, not a temperature of the proposer's own)
- hyperqwen [layer-compute] full-attention-compute: sparse attention budget when sparse attention is on
    nearest: any deliberate change to the model's arithmetic (names the change, not the budget that sets its strength)
- hyperqwen [model-conversion] draft-vocab-builder: which extra scripts are appended to the draft vocabulary and under what row budget
    nearest: the data a derived piece is selected or fitted from, and what is eligible for it (eligibility, not forced inclusion of rows outside the counted selection with its own budget)
- hyperqwen [model-conversion] gptq-requantizer: bits and group size; no act-order so the kernel needs no index
    nearest: precision per kind of weight (names the precision, not the quantisation method or its options chosen for kernel compatibility)
- hyperqwen [positional-state-store] kvarn-staging-quantizer: keep retired fp16 sinks resident; evict oldest first only when slots run dry
    nearest: which positions are kept at higher precision than the stored format (names what is kept, not when or in what order the higher-precision copies are evicted)
- hyperqwen [sampling] sampler: use one top-k selection instead of a full-vocabulary sort when every request's top-k is small
    nearest: the kernel used for the sampling arithmetic, and how it changes with the number of rows (here it changes with the requested settings, not the rows)
- hyperqwen [state-tiering] kv-offload-tier: which groups count as draft attention for the tier
    nearest: which kinds of state the slower tier holds
- ninfer [media-preparation] media-preparer: preprocess cache capacity and live payload budget
    nearest: caching of prepared media and its key
- ninfer [memory-planning] startup-memory-planner: how much headroom planning may consume versus what must stay free after initialization
    nearest: the reserve left free
- ninfer [model-loading] shard-materializer: whether a slice can be expressed value-preservingly, else the format rejects it
    nearest: whether weights are re-encoded at load and how
- ninfer [prefix-reuse] context-resource-manager: attention-owner rank chosen by load balance, then longest local prefix
    nearest: which device restored state is placed on
- ninfer [sequence-lifecycle] model-session: full permit before verify that covers the later commit peak
    nearest: a sequence's state allocated up front or grown on demand
- ninfer [step-execution] rank-program: where host handoffs split device work (grammar mask, CPU experts, final acceptance)
    nearest: cutting a step into parts so that work on two devices overlaps
- splash [calibration] ane-ffn-calibrator: the minimum predicted gain to enable the split
    nearest: the rule that accepts or rejects a measured result
- splash [configuration] configuration: defaults for each flag (decode share, idle release, KV and state formats, verify rows, cache quota and writes, ANE)
    nearest: which settings that change output are on by default, and in which profile (most of these defaults do not change output)
- splash [draft-policy] verify-row-budget: refit interval, label window, decay, prior strength
    nearest: how fresh the signals it decides from must be
- splash [expert-cache] expert-store: a size used by only one block holds all its experts in its floor
    nearest: whether it arranges, compacts or pins what it holds by size
- splash [expert-fetch] expert-loader: one round for decode, half the staging per round for prefill
    nearest: staging area and how many fetches at once
- splash [model-loading] weight-image-loader: repack on GPU through a fixed staging buffer
    nearest: whether weights are re-encoded at load and how (which device does the re-encoding is not named)
- splash [output-constraint] thinking-budget: where in the checked rows the forced end starts
    nearest: how it applies to proposed tokens that are not yet accepted
- splash [output-interpretation] output-parser: hold text that may begin a stop string
    nearest: stop conditions and their order
- splash [prefix-reuse] composite-state-cache: retire rolling checkpoints once a newer one is published
    nearest: what earns stored state its retention: recency, cost to rebuild, or actual reuse
- splash [prompt-reading] prefill-runner: abandon a paused command for higher-priority work (nothing committed)
    nearest: what state is kept when reading is interrupted or cancelled
- splash [residency-policy] slot-recycler: scans leave no ghosts and move no hits
    nearest: the replacement rule (whether bulk scans count as use is not named)
- splash [row-source] ple-row-store: prefetch as a hint
    nearest: prefetching rows for coming or drafted tokens (the mechanism, hint or binding read, is not named)
- splash [sampling] token-selector: sampling policy per lane
    nearest: the chain of steps and their order
- splash [state-tiering] ssd-cache-tier: share of writes in flight per kind (reclaim, copy ahead, write-through)
    nearest: share of writes in flight per kind of state (here the kinds are purposes of a write, not kinds of state)
- splash [state-tiering] write-behind: minimum depth and delay before copying
    nearest: copying ahead of need
- splash [state-tiering] write-behind: copy on a temporary tier only under demand
    nearest: copying ahead of need
- splash [state-tiering] kv-spill-controller: keep dense history, tail window and in-flight prefill groups in fast memory
    nearest: which kinds of state the slower tier holds
- splash [step-scheduler] request-scheduler: contended prefill cut rows from measured time with a floor
    nearest: sequences and rows per step
- splash [telemetry] telemetry: log only transitions
    nearest: what is recorded by default and what on request

