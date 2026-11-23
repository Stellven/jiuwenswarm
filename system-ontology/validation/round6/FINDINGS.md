# Node types draft 0.6: independent checks, round6

44 types, 500 choices. Thresholds were fixed on 2026-11-16 in `validation/criteria.yaml`, before this draft was written.

| Check | Result | Threshold | |
|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 238/240 = 99% | at least 90% | pass |
| Decisions plainly covered by a choice | 660/715 = 92% | at least 80% | pass |
| Decisions covered only loosely | 53/715 = 7% |  |  |
| Decisions not covered | 2/715 = 0% | at most 5% | pass |
| Claims an engine contradicts | 15 | at most 0 | FAIL |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 14 |  |  |
| Parts assigned to the wrong type in the reference | 0 |  |  |

## Per engine

| | strata | ds4 | hyperqwen | ninfer | splash |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 246 | 115 | 116 | 104 | 134 |
| Plainly covered | 96% | 90% | 91% | 92% | 90% |
| Not covered | 0% | 0% | 0% | 0% | 1% |
| Contradicted claims | 3 | 0 | 3 | 6 | 3 |
| Unnamed causes at a listed level | 3 | 4 | 3 | 2 | 2 |
| Relaxed `should` rules not yet noted | 0 | 1 | 0 | 1 | 0 |
| Inventory entries the source corrects | 4 | 5 | 0 | 1 | 3 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 224 | 16 | 0 |
| rater-b | 205 | 35 | 0 |

## Disagreements on type

- hyperqwen/pool-layout-planner: reference state-pool; rater-a memory-planning, rater-b state-pool — rater-a: Choosing the shared page geometry and per-kind block size is a state-pool sizing choice, while the admission capacity computation is memory planning. | rater-b: Plans page geometry and admission capacity at startup (memory planning) but hands out no pages at run time (pool job).
- splash/thinking-budget: reference output-constraint; rater-a output-constraint, rater-b output-interpretation — rater-b: Forced end-of-thinking tokens enforce a reasoning budget (interpretation) but also force tokens like a constraint, which the types split.

## Wrong assignments


## Contradicted claims

- strata [engine-supervision] engine-client: effect_on_output: exact (it passes requests on unchanged); defines (it rewrites request settings on the way to the engine)
    evidence: On a failed start it starts the engine again with no drafter after an out-of-memory error, or with the MTP drafter when DFlash2 did not start (engine-client decisions). Dropping or swapping the drafter changes the verify window widths, which the inventory records as numeric for this engine (draft-verifier, mtp-drafter, dflash2-drafter output_effect_when), and under STRATA_SPEC_PROB another draw: rounding and resampled, not listed.
    fix: add rounding and resampled: when a start retried with a reduced configuration drops or swaps a setting whose own effect is rounding or another draw, such as speculation or the proposal source
- strata [memory-planning] startup-memory-sizing: effect_on_output: exact (in itself); rounding (what it places where decides which device computes something, or a size it sets changes how the computation is cut)
    evidence: The cache size it sets decides whether the default route tail skip (omitting low-ranked missed experts, an approximation) is on: the skip is off by default when at least 90% of experts are in the GPU cache (src/program/generate.cpp:12785-12817). A different slot count can therefore turn a default approximation on or off, which is the approximate level, not listed.
    fix: add approximate: when a size it sets decides whether a default approximation of another node is in effect, such as omitting low-ranked selected blocks when few enough are cached
- strata [residency-policy] adaptive-tier: effect_on_output: exact (in itself); rounding (what is resident decides which device computes a block)
    evidence: With the tail skip on (the CUDA serving default), a missed expert routed only at rank 7 or lower is neither fetched nor computed (expert-dispatch decisions; generate.cpp:12776-12822). What the adaptive tier keeps resident decides which selected experts are missed and hence omitted, so its swaps change which experts the output omits, beyond rounding.
    fix: add approximate: when the dispatch omits low-ranked blocks that are not resident, what it keeps resident decides which are omitted
- hyperqwen [calibration] calibration-data-capture: effect_on_output: exact (in itself), rounding (split between devices / restore vs recompute), approximate (feeds a lossy conversion or reduced-precision path)
    evidence: Its captured Hessians feed GPTQ of the MTP module and the DFlash2 drafter, whose quantization 'changes only acceptance' (gptq-requantizer output_effect_when), and its self-generated outputs are what draft-vocab-builder counts to choose the draft vocabulary. Both change only pieces used for proposals: under sampling with acceptance using q this is `resampled` (output_principles 3), a level the type does not list.
    fix: Add `resampled` when its results feed a conversion or selection of pieces used only for proposals, and acceptance under sampling uses the proposals; keep `approximate` for results that feed a lossy conversion of what the full model computes.
- hyperqwen [engine-supervision] engine-core-loop: effect_on_output: exact when it passes requests on unchanged; defines when it rewrites request settings
    evidence: Its one decision is async scheduling (plan step N+1 while step N runs). Under it the verify-length count is ignored and 'async scheduling pads every decode step to the full draft count' (request-scheduler, verify-length-controller), so the width of every verify block changes, and verify-length-controller records that block length changes rounding and greedy text. That is `rounding`, not listed for the type.
    fix: Add `rounding` when preparing the next step while the current one runs fixes the width of steps (for example the number of proposed rows checked) differently from serial planning.
- hyperqwen [state-pool] paged-block-pool: effect_on_output: exact (in itself), approximate (the pool fixes a quantised stored format)
    evidence: The pool owns 'the free queue (eviction order)' and decides 'order in which freed blocks enter the free queue' (mamba-align-checkpoint-order.patch); that order decides which cached prefix blocks and recurrent snapshots survive, and prefix-cache records that greedy text differs between a hit and a miss (different chunking and rounding). The pool's own choice therefore reaches `rounding`, which the type does not list (output_principles 1 and 4 would put it there).
    fix: Add `rounding` when the order in which it reuses freed pages decides which stored state survives for reuse, and reused state differs in rounding from a fresh read.
- ninfer [draft-proposal] mtp-drafter: effect: exact, when: greedy decoding with exact acceptance
    evidence: Greedy acceptance is exact agreement with the verify block's argmax, but which positions fall in which verify block depends on how many proposals were accepted earlier; verify-block arithmetic and the folded recurrent state differ from token-by-token decoding (mtp-drafter correction; state-commit output_effect_when). The draft count is fixed, so the width condition under rounding does not apply; the cause is the placement of block boundaries.
    fix: exact: greedy decoding with exact acceptance and checked blocks computed as single-token decoding would; rounding: the proposals decide where checked blocks begin and end, and block arithmetic differs from single-token decoding
- ninfer [draft-proposal] block-drafter: effect: exact, when: greedy decoding with exact acceptance
    evidence: Same as mtp-drafter: with a fixed block width of 1 to 15, the accepted length under greedy acceptance decides the start of the next checked block, and checked-block arithmetic and committed state differ from single-token decoding (state-commit output_effect_when; draft-acceptance output_effect_when 'greedy matches the target argmax of the verify batch shape').
    fix: as for mtp-drafter: add to rounding 'the proposals decide where checked blocks begin, and checked-block arithmetic differs from single-token decoding'
- ninfer [memory-planning] startup-memory-planner: effect_on_output levels: exact; rounding when ... a size it sets ... changes how the computation is cut
    evidence: It sizes the shared context backing per rank (gives context-pool capacity). Admission and pausing follow that capacity (request-scheduler, context-pool 'admission uses placement'), so it bounds how many lanes share a decode or verify round; the rows in a round select 16-bit or 4-bit activations for AllowA4 projections (request-scheduler correction). By the type's own rounding condition and output principle 2, that reaches approximate, which the type does not list.
    fix: add approximate: a capacity it sets bounds the number of rows in a step, and that number selects a reduced activation precision that the weights permit or the kernels choose
- ninfer [model-conversion] draft-head-builder: effect: exact, when: it only re-arranges bytes, or changes only pieces used for proposals under greedy decoding
    evidence: Under greedy decoding the proposals decide how many tokens each verify round accepts, so they decide where the next verify block starts. Greedy output follows the verify block shape (corrections, mtp-drafter), and committed recurrent state is bit-identical to the same physical verify block, not to token-by-token decoding (state-commit output_effect_when; include/ninfer/ops/speculative_accept.h 22-44). A different draft head therefore moves block boundaries and changes rounding of later tokens.
    fix: exact under greedy decoding only where checked blocks are computed exactly as single-token decoding; otherwise rounding, because proposals move the boundaries of checked blocks
- ninfer [scoring] causal-scorer: effect_on_output levels: exact; rounding when the scored sequence is read in steps of another width than generation uses
    evidence: Scoring submits ExecutionUnitKind::Prefill units over windows of the sequence (src/models/qwen4_exp/session/scoring.cpp 40-70). Projections with an AllowA4 permit run 4-bit activations for steps of 5 or more tokens and 16-bit for 1 to 4 (src/ops/linear/swiglu/nvfp4/shapes/n34816_k5120/dispatch.cpp 22-36), so scores are computed at another activation precision than token-by-token generation: approximate, a level the type does not list.
    fix: add approximate: the width of the scoring steps selects a reduced activation precision that the weights permit or the kernels choose
- ninfer [scoring] causal-scorer: must: A score is computed by the same model, weights and kernels as generation. Where precision depends on the width of a step, the width the score was computed at is stated.
    evidence: Precision depends on step width (dispatch.cpp 22-36), but the scoring result is only the vector of log-probabilities (src/runtime/engine/causal_score_core.h 236-259; ScoreComplete.logprobs); no step width or activation precision is reported with it. Kernels also differ from decode (prefill route versus DecodeFusedA16).
    fix: make the width statement a should rule ('the width or activation precision a score was computed at is stated'), relaxed: one engine returns scores without it
- splash [residency-policy] slot-recycler: state: use counts, the ranking, or the current role of each region (and takes: how often each is used, a ranking made offline, or the size of the coming work)
    evidence: The part is adaptive replacement (ARC): it keeps a recently-once list, a recently-again list, two ghost lists of evicted keys and an adaptive target share, and takes hits, misses and whether a load is a scan. It keeps no use counts (inventory slot-recycler owns_state; runtime/model/SlotRecycler.hpp:11, 67-79, 110-137).
    fix: state: the use history it decides from (use counts, or recency lists with remembered evictions and an adaptive split between them), the ranking, or the current role of each region
- splash [resource-governing] memory-ledger: effect_on_output: exact (the only level listed, with no condition)
    evidence: The ledger's reclaim order takes, as its own victims, a Resident lane's KV by converting the lane to Spill, the paused prefill command (which reruns later) and units in use (inventory memory-ledger decisions; runtime/engine/MemoryLedger.hpp:79-81, 146-153). Conversion to Spill bounds the request's output by the SSD tier's active-KV quota and ends it there (corrections: kv-spill-controller changes_output), and evicting cached states decides whether a later request restores stored state or recomputes it, which the type of calibration itself counts as rounding. So by its own choice of victim it reaches rounding and defines.
    fix: exact in itself; rounding when what it reclaims decides whether a sequence's state is later restored or recomputed, or abandons work that is rerun with another cut; defines when its reclaim moves a sequence to a slower tier whose capacity then ends that sequence's output
- splash [scoring] option-scoring: effect_on_output: exact; rounding when the scored sequence is read in steps of another width than generation uses (no defines)
    evidence: The part renders its own fixed prompt shape (a fixed system instruction plus one JSON user payload, thinking disabled) around the caller's question and returns a softmax over the option slots only (server/dialects/scoring.py:24-31, 56-60). The probabilities returned are decided by that prompt by design: the defines level, which the type does not list.
    fix: add effect: defines, when: it renders its own prompt around the given text or options, or normalises the returned probabilities over the given options only

## New causes

- strata [calibration] speed-calibration: approximate — its measured choice of residency settings decides which selected blocks a default omission skips
    evidence: The calibration sweeps adaptive-tier settings (speed-calibration decisions) and the tail skip omits missed experts by default (generate.cpp:12776-12822); the listed approximate condition names only lossy conversion and reduced-precision paths.
- strata [model-loading] native-weight-loader: approximate — by default it selects a lower-precision stored copy of some weights the full model computes with, when the files carry one, instead of the higher-precision copy
    evidence: STRATA_HC_Q8 is on by default on CUDA when the shards carry the hyper-connection projections as Q8_0 (inventory decision; data/settings-register.json:12969); it reads Q8_0 instead of BF16 and changes tokens (docs/STRIX_HALO.md:191, 309: 94 of 250 tokens differ). The listed approximate condition names reduction while loading and the rounding condition names choosing among stored encodings; neither names choosing a lower-precision stored copy.
- strata [sequence-lifecycle] engine-command-loop: approximate — the number of sequences kept open turns a default approximation of another node off, because that approximation would make one sequence's output depend on another's tokens
    evidence: The route tail skip default requires o.batch == 0 and is off with batch slots (src/program/generate.cpp:12779-12780, 12806); the slot count is this part's decision.
- ds4 [device-backend] gpu-backend: approximate — the kernel tier selects a reduced-precision path by the amount of stored context the step reads (number of stored compressed rows), not only by step width or device; it is also skipped while the work is being recorded into a graph
    evidence: ds4_cuda.cu 14787-14797: MXFP4 indexer only when n_comp >= 1024 and n_tokens >= 32, one GPU, not --quality, and not during stream capture
- ds4 [draft-policy] dspark-scheduler: approximate — under an acceptance rule that does not preserve the distribution, the decision whether to draft in a round decides whether that round's tokens follow the sampling distribution or the greedy one
    evidence: ds4.c 88383-88384: default (non-exact) acceptance compares the draft with the argmax at any temperature; the scheduler pauses and resumes drafting from acceptance counts (ds4.c 63216-63335)
- ds4 [draft-proposal] dspark-drafter: approximate — under an acceptance rule that does not preserve the distribution, how many tokens are proposed (the confidence stop) decides how many positions are taken greedily instead of sampled
    evidence: inventory draft-verify-commit output_effect_when; ds4.c 88383-88384 argmax comparison in default mode; drafter stops on a confidence threshold
- ds4 [output-interpretation] tool-call-codec: defines — it substitutes remembered generated text for the client's resubmitted version of earlier output when the next prompt is built
    evidence: inventory: LRU map from tool-call id to sampled text, replayed byte-identically into rendering instead of the client's JSON
- hyperqwen [model-loading] weight-loader: rounding — re-encoding the stored weights into the form a kernel reads cannot represent every stored value, so a rare value is moved by one quantisation step
    evidence: marlin-int8-negative-scales.patch folds the sign of negative group scales into the int4 codes for the int8-activation kernel; 'numerically identical except that the rare code -8 becomes -7 (one LSB) in flipped groups'. The type's rounding conditions name only a change of floating-point width or a choice among stored encodings.
- hyperqwen [positional-state-store] kvarn-staging-quantizer: approximate — whether state reused by a later request is still held at the higher staging precision or has been converted to the stored quantised format depends on slot pressure from other sequences
    evidence: kvarn-staging-quantizer keeps finished requests' first blocks in fp16 'until slots run short' and evicts the oldest only when slots run dry; output_effect_when says these retained sinks keep multi-turn reuse closer to unquantised. The type names only 'stored quantised or compressed', not a precision of reused state that depends on concurrent load.
- hyperqwen [step-scheduler] request-scheduler: approximate — whether a prompt chunk runs alone in a step or shares it with other sequences selects a reduced-precision kernel (not only how many rows the step holds)
    evidence: patches/prefill-attn-int8.patch: the int8-QK prefill kernel 'fires only for single-request prefill chunks (max_seqlen_q > 16, one request in the varlen batch)'; with other requests in the batch the step falls back to FA2. The type's approximate condition names only the number of rows.
- ninfer [expert-dispatch] hybrid-moe-dispatch: rounding — the split between devices follows which fetches have completed when the layer starts, so the same request can round differently from run to run
    evidence: GPU/CPU mask built from a snapshot of ready experts; output 'depends on which experts are ready at that moment' (inventory hybrid-moe-dispatch output_effect_when; offload-mode-switch output_effect_when)
- ninfer [sequence-lifecycle] model-session: approximate — a paused sequence released and replayed has its generated tokens re-read in wide chunks, so its rebuilt state is computed at another activation precision than the decode steps that first produced it
    evidence: pause action 'release and replay' (model-session decisions); chunked-prefill replays committed tokens in chunks; AllowA4 projections use 4-bit activations at 5 or more tokens per step (dispatch.cpp 22-36)
- splash [sequence-lifecycle] lane-admission: rounding — a paused sequence that is released and later resumed recomputes its generated history by the prompt-reading path, with other kernels and cuts than the decode steps that first produced it
    evidence: lane-admission suspends lower-ranked lanes which later replay from cache; runtime/engine/Engine.hpp:701-705: generated history that a resumed lane replays is its own; kernel-selector chooses a different tile for prefill rows
- splash [step-scheduler] request-scheduler: approximate — the number of rows it puts in a prompt chunk decides whether the chunk reaches a row threshold measured at startup, above which part of each dense block is computed on a second device at lower precision; neither the weights nor the kernel tier select it
    evidence: ane-ffn-calibrator picks the least chunk rows; the split runs only for rows >= minimumRows (runtime/ops/AneFfn.cpp:470-474); the split computes W8A8 on the Neural Engine (ane-ffn-split, on by default per corrections); request-scheduler sizes contended prefill cuts from measured time

## Relaxations

- ds4 [prefix-reuse] disk-kv-checkpoint-store: Stored state is reused only where the model, the weights' precision, the settings and the prefix match what it was made for. — Besides cross-precision reuse (named), the stored key holds only model id, routed quant bits and context; settings that change the stored state, such as directional steering and the activation-precision mode (--quality), are not keyed, so state made under one is restored under another (ds4_kvstore.h 36-58, ds4_kvstore.c 518-519, 852-858).
- ninfer [layer-compute] layer-compute: An approximation that is in effect is stated with the run's settings. — 4-bit activations for AllowA4 uses are permitted only in the converted artifact and taken whenever a step has 5 or more tokens; no run setting, option or log states it, and it cannot be turned off without reconverting (permits in src/artifact/schema.cpp and src/models/common/bindings.cpp; no reference in src/product/config or observability).

## Inventory errors

- strata native-weight-loader.output_effect_when: recorded 'bit_exact when a tensor uploaded unchanged; numeric when native head or projections; approximate when a BF16 projection is converted to Q8_0 at load'; source shows "The default STRATA_HC_Q8 read of the shards' Q8_0 hyper-connection copies changes tokens beyond rounding (docs/STRIX_HALO.md:191-192, 309; data/settings-register.json:12969); it is on by default on CUDA for such files and is not listed as approximate."
- strata startup-memory-sizing.output_effect_when: recorded 'bit_exact when the sizing only moves where bytes are read from; numeric when the slot count changes which experts the GPU computes'; source shows 'The slot count also decides whether the route tail skip is on by default (off when at least 90% of experts are cached), which changes output beyond rounding (src/program/generate.cpp:12785-12817).'
- strata engine-command-loop.output_effect_when: recorded 'bit_exact when batch slots off'; source shows 'With batch slots off the tail skip is on by default on CUDA (unless nearly all experts are cached or experts are NVFP4), so the default solo path is not bit_exact; with slots on it is off (src/program/generate.cpp:12776-12822, condition o.batch == 0).'
- strata adaptive-tier.output_effect: recorded 'none; bit_exact when the GPU and CPU expert kernels round identically'; source shows 'Under the default tail skip, residency decides which low-ranked experts are omitted (src/program/generate.cpp:12776-12822; src/core/expert_source.cpp:4964), so swaps change the output beyond rounding.'
- ds4 request-scheduler.output_effect: recorded 'none'; source shows 'ds4_server.c 12431-12439, 12473-12474: the prefill quantum, and so where a prompt is cut into chunks, is 128 tokens while any generation is active and 2048 or more otherwise; chunk boundaries depend on concurrent load, so the effect is at least numeric (and, with the CUDA Q8_1 tier, beyond last bits).'
- ds4 cross-gpu-transfer.output_effect: recorded 'none'; source shows 'ds4_gpu_mgpu.h 184-189: ds4_gpu_add_xdev_tensor adds partial results from two GPUs for tensor-parallel reductions, so the sum order differs from one device; numeric.'
- ds4 tool-call-codec.output_effect: recorded 'none'; source shows 'ds4_server.c 14323-14396: repaired tool-call text replaces the generated text, and a failed parse of a non-streaming request reruns generation with a model-visible error; changes_output.'
- ds4 dspark-scheduler.output_effect_when: recorded 'Which path advances a token changes summation order only (numeric)'; source shows 'ds4.c 88383-88384: in the default mode a draft is accepted when it equals the argmax at any temperature, so whether a round drafts changes the distribution at temperature above 0; changes_output.'
- ds4 (missing part).parts: recorded 'no part for recorded execution graphs'; source shows 'ds4_cuda.cu 1118-1216 (also 9923, 24567): CUDA decode steps are captured as graphs per layer and island key with a warm pass, replayed on later steps, and fall back to eager encoding when capture or replay fails; this is a graph-capture part the inventory omits.'
- ninfer expert-priority-table.output_effect: recorded 'none'; source shows 'its per-layer order is the fixed GPU-resident set for offload (src/models/common/moe/offload/plan.cpp 228-234 spec.priority) and assigns experts to ranks under EP2 (src/models/qwen4_exp/parallel/plan.cpp 34-37), so it decides which device computes an expert: numeric'
- splash lane-admission.output_effect: recorded 'none'; source shows "A suspended request resumes by replaying its generated history through prefill (runtime/engine/Engine.hpp:695-707), so the continuation is computed from recomputed state with prefill kernels and cuts, not the decode steps' state: numeric."
- splash option-scoring.output_effect: recorded 'none'; source shows 'server/dialects/scoring.py:24-31, 56-60: it renders a fixed system instruction and JSON payload of its own and softmaxes over the option slots, so the returned probabilities are decided here (changes_output).'
- splash memory-ledger.output_effect: recorded 'none'; source shows "runtime/engine/MemoryLedger.hpp:79-81, 146-153: one of its victim kinds is the conversion of a Resident lane to Spill, after which the request's output is bounded by the SSD quota (changes_output for that request)."

## Decisions not covered

- strata [expert-dispatch] expert-dispatch: omission of low-ranked misses is on by default only below a share of cached experts and never for one expert format (from the corrections)
    missing (threshold): the share of selected blocks already in fast memory above which omitting low-ranked selections is not on by default, and the weight formats for which it is never on by default
- splash [calibration] ane-ffn-calibrator: the minimum predicted gain to enable the split
    missing (threshold): the least gain a measured result must predict before the setting it supports is turned on

## Decisions covered loosely

- strata [configuration] run-config-generator: the speculative window and confidence floor written by default
    nearest: which settings that change output are on by default, and in which profile
- strata [configuration] run-config-generator: an option that differs from what setup last wrote is taken as a hand edit and kept, except options setup re-decides
    nearest: operator values, presets, measured values and defaults
- strata [draft-verification] draft-verifier: the exact gated rule is used only under a list of conditions; otherwise an older rule runs with a warning that its distribution is off
    nearest: the acceptance rule under sampling
- strata [draft-verification] draft-verifier: the commit graph is launched without waiting; readers elsewhere wait for it first
    nearest: commit at once or with the next step
- strata [memory-planning] startup-memory-sizing: lowest value the reserve is lowered to so that the minimum cache fits
    nearest: the order in which things are given up when memory is short, and when starting is refused
- strata [memory-planning] host-memory-admission: the engine may replace the arena by the file source on its own unless the operator fixed the RAM mode, named a shared arena or disabled the fallback
    nearest: an operator's explicit size against the computed one
- strata [prefix-reuse] resume-decision: reuse of any kind needs a checkpoint capacity above zero
    nearest: how many are kept and where
- strata [prompt-reading] prompt-path: which experts of a chunk may go to the CPU (routed here, not cached, not on a second accelerator, few enough tokens, readable in place) and fewest-tokens-first order
    nearest: how the work of a chunk is shared with a second device, and when sharing is abandoned
- strata [row-source] ngram-reader: in direct mode, read one random page after a quiet interval until a time after the last request (storage keep-alive)
    nearest: warming the table in the background and when to stop
- strata [step-execution] window-loop: per window, a device-planned graph when every expert of the stage is cached, else a graph that signals the host per layer
    nearest: one step as a whole, or driven layer by layer
- ds4 [device-backend] gpu-backend: Prefill workspace shared between sessions in batch mode
    nearest: scratch and command buffers (sharing between sequences is not named)
- ds4 [expert-cache] routed-expert-cache: Metal cache buffers locked in memory; a lock failure lowers the effective limit
    nearest: what is done when the cache cannot be allocated at its planned size (no choice names whether the cache's own memory is locked)
- ds4 [positional-state-store] dense-attention-cache: Full dense cache with a length cap versus compact latent cache
    nearest: precision and layout of stored state
- ds4 [residency-policy] expert-eviction-policy: Heat increments on every selection, misses included, not only on hits
    nearest: the replacement rule (what counts as a use is not named)
- ds4 [residency-policy] expert-cache-preloader: Preload cap in automatic mode
    nearest: what the cache holds before any request (how much is preloaded is not named)
- ds4 [row-source] engram-prewarm: Warm only when model, runtime, table and a reserve fit physical memory
    nearest: warming the table in the background and when to stop (names stopping, not the condition to start)
- ds4 [row-source] ngram-row-reader: Prefetch only for chunks above a size and with a bounded buffer
    nearest: prefetching rows for coming or drafted tokens
- ds4 [sampling] tool-call-sampling-mode: Which tag sets count as structure
    nearest: whether settings change per position, for example greedy on structure and sampled on content
- ds4 [sequence-lifecycle] slot-router: Ordered tiers of match kinds (transcript, tool bindings, rewind, token prefix, thinking-visible, rendered text)
    nearest: which store is used when several hold a match (prefix-reuse, also type); the order among kinds of match is not named
- ds4 [sequence-lifecycle] slot-router: Continuations pinned to their slot
    nearest: how a request is matched to a place: a slot or a lane
- ds4 [session-persistence] session-payload-serializer: Under tensor parallelism, load only tokens and re-prefill
    nearest: in which configurations saving and restoring is offered (restoring by recomputation from tokens is not named)
- hyperqwen [configuration] launch-profile-resolver: drafter kind and number of draft tokens
    nearest: named profiles and what each fixes
- hyperqwen [configuration] launch-profile-resolver: pin the pool by bytes or by utilisation; skip the pin under tensor parallelism
    nearest: rules that derive a setting's default from other settings and machine facts
- hyperqwen [configuration] launch-profile-resolver: prefix caching on with align-mode recurrent state, and the snapshot retention interval
    nearest: which settings that change output are on by default, and in which profile
- hyperqwen [draft-proposal] mtp-drafter: draft from the target's top-k/top-p support; optional draft temperature scale
    nearest: the set of tokens proposals are restricted to (the temperature scale of the proposer is not named)
- hyperqwen [draft-verification] draft-acceptance: draft sampling must be probabilistic so the draft distribution is passed (otherwise acceptance is strictly stricter)
    nearest: the acceptance rule under sampling
- hyperqwen [layer-compute] full-attention-compute: sparse attention budget when LSA is on
    nearest: any deliberate change to the model's arithmetic (names the change, not its budget)
- hyperqwen [model-conversion] draft-vocab-builder: which extra scripts (CJK, Cyrillic) are appended to the draft vocabulary and under what row budget
    nearest: the data a derived piece is selected or fitted from, and what is eligible for it (forced inclusion of a reserved share is not eligibility)
- hyperqwen [model-partitioning] tensor-parallel: allocator without expandable segments so graph buffers can be exported between processes
    nearest: which other engine features may be combined with splitting the model, and which are refused
- hyperqwen [positional-state-store] kvarn-staging-quantizer: flush a finished request's full block (a later prefix hit may read it) but discard a partial one
    nearest: when state held in a staging precision is converted to its stored format (says nothing of what a finished sequence's staged state becomes)
- hyperqwen [positional-state-store] kvarn-staging-quantizer: draft passes after the first only allocate staging slots, never flush
    nearest: when state held in a staging precision is converted to its stored format (not tied to whether the positions can still be rejected)
- hyperqwen [state-tiering] kv-offload-tier: which groups count as draft attention (only the drafter's sliding-window groups)
    nearest: which kinds of state the slower tier holds
- ninfer [expert-dispatch] hybrid-moe-dispatch: large work (stream whole layer) versus small work (split with CPU) by a per-layer token threshold
    nearest: the share of misses fetched now against left to another device
- ninfer [media-preparation] media-preparer: preprocess cache capacity and live payload budget
    nearest: caching of prepared media and its key
- ninfer [model-conversion] checkpoint-converter: storage format and encoding method per role (import encoded, grouped absmax, FP8 maxabs, stored-scale MSE search, direct cast)
    nearest: precision per kind of weight (names the target precision, not the algorithm that fits codes and scales)
- ninfer [model-loading] shard-materializer: whether a per-rank slice can be expressed value-preservingly in its stored format, else it is rejected
    nearest: whether weights are re-encoded at load and how
- ninfer [prefix-reuse] context-resource-manager: attention-owner rank under attention data parallelism: load balance bound, then longest local prefix
    nearest: which device restored state is placed on
- ninfer [residency-policy] offload-mode-switch: refill pace of the extra cache after returning to small work (bytes and batches per call)
    nearest: the gain a change must bring, and a limit on changes per round
- ninfer [sequence-lifecycle] model-session: a full permit reserved before verify that covers the later commit peak
    nearest: a sequence's state allocated up front or grown on demand
- ninfer [step-execution] rank-program: where host handoffs (grammar mask, CPU experts, final acceptance) split device work
    nearest: cutting a step into parts so that work on two devices overlaps
- splash [configuration] configuration: defaults for each flag (decode share, idle release, KV and state formats, verify rows, cache disk quota and writes, ANE on/off)
    nearest: which settings that change output are on by default, and in which profile (defaults of settings that do not change output are not named)
- splash [draft-policy] verify-row-budget: refit interval, label window, decay, prior strength
    nearest: how fresh the signals it decides from must be
- splash [expert-cache] expert-store: release one chunk, or all to floor under critical pressure
    nearest: which part is released or regrown first under memory pressure (how much is released at each pressure level is not named)
- splash [expert-cache] expert-store: a size used by only one block holds all its experts in its floor
    nearest: whether it arranges, compacts or pins what it holds by size
- splash [model-loading] weight-image-loader: repack on GPU through a fixed staging buffer
    nearest: staging buffers and reader threads used while loading (nothing names which device does the re-encoding)
- splash [output-constraint] thinking-budget: where in the 8 rows the end starts
    nearest: how it applies to proposed tokens that are not yet accepted
- splash [output-interpretation] output-parser: hold text that may begin a stop string
    nearest: stop conditions and their order (holding partial matches is the type's must rule, not a choice)
- splash [prefix-reuse] composite-state-cache: retire rolling checkpoints once a newer one is published
    nearest: what earns stored state its retention: recency, cost to rebuild, or actual reuse
- splash [row-source] ple-row-store: prefetch as a hint
    nearest: prefetching rows for coming or drafted tokens (that a prefetch is best-effort and its failed rows are dropped is not named)
- splash [sampling] token-selector: sampling policy per lane
    nearest: the chain of steps and their order
- splash [state-tiering] write-behind: minimum depth and delay before copying
    nearest: copying ahead of need
- splash [state-tiering] kv-spill-controller: keep dense history, tail window and in-flight prefill groups Full
    nearest: what leaves first
- splash [telemetry] telemetry: log only transitions
    nearest: what is recorded by default and what on request

