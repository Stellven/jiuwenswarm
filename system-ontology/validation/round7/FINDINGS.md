# Node types draft 0.7: independent checks, round7

44 types, 502 choices. Thresholds were fixed on 2026-11-16 in `validation/criteria.yaml`, before this draft was written.

| Check | Result | Threshold | |
|---|---|---|---|
| Blind agreement: every reader and the reference name the same type | 239/240 = 100% | at least 90% | pass |
| Decisions plainly covered by a choice | 664/716 = 93% | at least 80% | pass |
| Decisions covered only loosely | 49/716 = 7% |  |  |
| Decisions not covered | 3/716 = 0% | at most 5% | pass |
| Claims an engine contradicts | 5 | at most 0 | FAIL |
| Causes of an output effect not yet named, at a level the type lists (counted as contradictions up to draft 0.5) | 23 |  |  |
| Parts assigned to the wrong type in the reference | 3 |  |  |

## Per engine

| | strata | ds4 | hyperqwen | ninfer | splash |
|---|---|---|---|---|---|
| Decisions (engine-specific excluded) | 248 | 115 | 115 | 104 | 134 |
| Plainly covered | 94% | 92% | 90% | 91% | 94% |
| Not covered | 0% | 1% | 0% | 1% | 0% |
| Contradicted claims | 2 | 1 | 0 | 0 | 2 |
| Unnamed causes at a listed level | 6 | 2 | 5 | 3 | 7 |
| Relaxed `should` rules not yet noted | 2 | 1 | 1 | 0 | 2 |
| Inventory entries the source corrects | 6 | 1 | 1 | 0 | 1 |

## Readers' own fit marks

| Reader | clean | partial | none |
|---|---|---|---|
| rater-a | 220 | 20 | 0 |
| rater-b | 220 | 20 | 0 |

## Disagreements on type

- hyperqwen/pool-layout-planner: reference state-pool; rater-a memory-planning, rater-b state-pool — rater-a: It mainly fixes the pool's page geometry, a choice listed under the state pool, though it hands out no pages. | rater-b: Page layout belongs to state-pool, but computing how many requests can be admitted is memory-planning.

## Wrong assignments

- ds4 gpu-backend: device-backend -> device-backend, also graph-capture. Per the round6 correction, CUDA decode steps are captured as graphs per layer and island key with a warm pass, replayed later, and fall back to eager encoding on failure (ds4_cuda.cu 1118-1216); that code lives in the backend this part covers, so its graph-capture job has no type in the assignment.
- hyperqwen drafter-free-chains: draft-policy -> draft-policy, also draft-proposal. Besides deciding to skip the drafter, it forms the proposals itself (whole verify blocks of point-mass drafts from the lookup); under draft-policy alone its own effect would be claimed exact, while its proposals set the checked block width and, under sampling, the draw.
- hyperqwen tensor-parallel: model-partitioning -> model-partitioning, also device-communication. The part also runs the collectives (custom all-reduce) that combine partial results, and its recorded effect, a different reduction order, is device-communication's rounding case; no other part of the inventory does that job.

## Contradicted claims

- strata [draft-proposal] mtp-drafter: output_principles: 'A change to pieces used only for proposals is exact under greedy decoding with exact acceptance only where ... Otherwise it is rounding, because proposals move the boundaries of checked blocks.'
    evidence: The default route tail skip omits a missed expert only when every token of the verify window routes it at rank 7 or lower (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822). The drafts in a window therefore decide which experts are omitted for the accepted rows, so under greedy decoding a change to the drafter changes output beyond rounding.
    fix: Otherwise it is at least rounding, and approximate where a default omission is decided over all rows of the checked block, so that the proposals decide what is omitted for accepted rows.
- strata [session-persistence] session-files: effect_on_output: exact when loaded into the model and settings it was written for; approximate when loaded into other weights or settings (no rounding level)
    evidence: The file's configuration identity leaves out the prompt chunk and the expert tier (session-files decisions), so a file written under one chunking or expert placement is accepted under another; the restored state then carries the rounding of the run that wrote it, which differs from a fresh read by rounding only (prompt-path, checkpoint-chain and resume-decision record chunking and placement as numeric).
    fix: Add rounding: when it is loaded under settings its identity leaves out that change only rounding, such as the prompt chunk or where blocks are computed.
- ds4 [device-communication] pipeline-parallel: effect_on_output: exact when it only moves data, or combines in the same order as one device would; rounding when it combines partial sums in another order
    evidence: Correction (round4), ds4_distributed.c 790-793, 949-955: activations crossing stages can be sent as FP8 E4M3, a lossy reduction (changes_output); f16 is a width change. The moving part's own work reaches approximate, which device-communication does not list (model-partitioning, the part's main type, does).
    fix: Add 'approximate: it sends activations in a lossy reduced format' and widen rounding to 'it combines partial sums in another order, or sends activations at another floating-point width'.
- splash [model-loading] weight-image-loader: effect_on_output exact when: weights are used as stored, re-encoded without changing their values, or reduced only for proposals under greedy decoding
    evidence: The draft is quantized from BF16 to 4-bit at load (inventory decisions and output_effect_when). Under greedy decoding the proposals decide how many tokens are accepted and so where the next 8-row verify block starts; for MoE they also set the verified row count (verify-row-budget reads draft confidence). Kernel choice and split order follow rows and lanes (kernel-selector, KernelSelection.cpp), and acceptance-commit records greedy output as the target's 'up to kernel numerics'. So a proposal-only reduction reaches rounding under greedy decoding here.
    fix: exact when ... or reduced only for proposals under greedy decoding where checked blocks are computed exactly as single-token decoding would; add to rounding: it reduces weights used only for proposals and the proposals move the boundaries or width of checked blocks (as model-conversion already says)
- splash [residency-policy] slot-recycler: summary: Decide which selectively used weights are kept in fast memory
    evidence: The same recycler also chooses the slot of the shared hot cache of spilled K/V blocks (takes block keys from spilled-kv-reader, gives it slots to fill); its job is not limited to selectively used weights.
    fix: Decide which selectively used weights, or other blocks read back from slower storage into a bounded fast cache, are kept in fast memory

## New causes

- strata [draft-policy] draft-policy: approximate — under an acceptance rule that does not preserve the distribution, the source and width it chooses each round change the distribution of the output
    evidence: Same older acceptance rule (src/program/generate.cpp:3152-3175); the policy chooses source and width per round. affects_output_through item 4 names only drafting versus not drafting deciding greedy versus sampled positions.
- strata [draft-proposal] mtp-drafter: approximate — under an acceptance rule that does not preserve the distribution, the proposer's own probabilities (a masked, unnormalised measure) enter acceptance and shift the output distribution
    evidence: draft-verifier decisions: with STRATA_SPEC_PROB=1 the pick gate uses the draft measure; where the gated rule is not usable the older rule runs and the engine warns that its distribution is off (src/program/generate.cpp:3152-3175). The type's approximate condition names only how many positions are taken greedily.
- strata [prompt-preparation] prompt-builder: defines — control-token text written inside a message is encoded as plain text, so the tokens differ from encoding the rendered text whole with the model's tokenizer
    evidence: prompt-builder must_never: only the template's own control tokens become control tokens; control-token text inside a message is encoded as plain text.
- strata [prompt-reading] prompt-path: rounding — the share of a chunk's work it hands to a second device is set from running averages of measured times, so the same prompt can be split, and rounded, differently from run to run
    evidence: prompt-path decisions: the CPU share is the accelerator's time per expert over the sum of both times, as running averages; sharing is switched off when the measured time does not improve. Principle 2 names which device computes, not that the choice follows timing. Cannot tell cleanly whether this is the node's own effect (it decides the share) or through the second device that computes it.
- strata [residency-policy] adaptive-tier: approximate — where an opt-in routing change favours resident blocks, what it keeps resident changes which blocks are selected, not only where they are computed
    evidence: expert-router decisions: STRATA_ROUTE_PRIOR re-picks the top 10 with a bonus for experts resident in fast memory; STRATA_ROUTE_RESIDENT swaps a non-resident tail expert for a resident one. Opt-in, so principle 4 (default omission) does not name it; the same holds for the cache size set by startup-memory-sizing.
- strata [secondary-compute] cpu-expert-pool: rounding — its arithmetic for one row depends on how many rows share the job, because grouped kernels carry every token routed to an expert
    evidence: draft-verifier output_effect_when: numeric with a native IQ pack and experts computed on the CPU, because grouped kernels round differently by window width; cpu-expert-pool records a window-invariant arithmetic option. The type's rounding condition names only rounding differently from the main device.
- ds4 [device-communication] pipeline-parallel: rounding — activations are sent between devices at a narrower floating-point width than they were computed in
    evidence: inventory decision 'Activation bits on the wire'; correction: f16 on the wire is numeric. device-communication names rounding only for a changed combining order.
- ds4 [model-loading] weight-binder: rounding — whether a quantised weight is re-encoded into a wider floating-point copy at load depends on the memory budget left on the device, so which tensors are computed from the re-encoded copy varies with memory
    evidence: ds4.c 3601-3646 and ds4_cuda.cu 5330-5378, 1562-1673: on CUDA, Q8_0 matrices are preloaded as dequantized F16 (or F32) copies while a VRAM budget allows; the rest are read in Q8_0. The type names re-encoding that changes width, not that it is conditional on remaining memory.
- hyperqwen [graph-capture] compile-and-warmup: rounding — compiled kernels specialised on a step dimension such as batch size run different code, and so may round differently, per value of that dimension
    evidence: decision 'which Triton kernels must not specialise on batch size' (patches/vllm-pr64137-logits-stats-no-specialize.patch, vllm-pr66026-gather-draft-sampled-no-specialize.patch). The type's rounding condition names only a recorded graph fixing a variant that differs from the unrecorded path.
- hyperqwen [layer-compute] full-attention-compute: approximate — a reduced-precision kernel is selected by whether a prompt chunk runs alone in its step (and above a width), so one sequence's precision depends on whether others share the step
    evidence: decision 'int8-QK prefill only for one-request chunks over 16 tokens'; patches/prefill-attn-int8.patch gate. The type's condition names only the number of rows; step-scheduler names the sharing as its through effect, layer-compute does not name it as a cause of its own.
- hyperqwen [model-loading] weight-loader: approximate — while preparing weights it marks, per layer by name, which layers the matrix kernels run with reduced activation precision, from a run-time setting
    evidence: gives linear-gemm 'int8-activation selection per layer'; patches/marlin-int8-layer-select.patch (include/exclude patterns applied in process_weights_after_loading). model-loading has no affects_output_through, and output_principles names a permit recorded at conversion, not a selection applied at load.
- hyperqwen [prefix-reuse] prefix-cache: approximate — a hit reads reused positions in the quantised stored format, where a fresh read of the same prompt would still hold the last positions of each chunk at the staging precision; the level of the difference follows how much staged state the store kept
    evidence: kvarn-staging-quantizer: fp16 staging until a 128-token tile fills, retained fp16 sinks 'keep multi-turn reuse closer to unquantised'; prefix-cache output_effect_when. The type's approximate conditions name other weights or settings and another activation precision, not another stored precision. Cannot fully tell whether this is prefix-reuse's own effect or the stored-state node's effect through reuse (output_principles last item speaks of rounding and precision of the producing step, not of a stored format that differs from a fresh read).
- hyperqwen [sampling] sampler: rounding — the sampling kernel is chosen by the number of rows in the step and by the settings of every request in it, so one request's arithmetic depends on the others in the batch
    evidence: decisions 'one topk when every request's top-k is at most 64' and 'multi-block row softmax for up to 16 rows' (patches/sampler-small-topk-fast-softmax.patch). The type's rounding condition is only 'the same chain differs only in floating point'.
- ninfer [device-communication] collective-communication: rounding — partial sums are combined at the activation width rather than at a wider accumulator width, so the combined result differs from a single-device sum even where the order is the same
    evidence: inventory output_effect_when: reduction order differs from a single-rank sum; no FP32 forced. The type names only combining in another order.
- ninfer [layer-compute] layer-compute: approximate — the computation writes the per-position state it appends in a reduced stored precision (8-bit or 4-bit encodings); the type has the matching choice but its approximate condition names only activations and approximated operations
    evidence: inventory does: KV append in the chosen encoding; decision: KV encoding (bf16, int8, fp8, nvfp4, k8v4). The same level is claimed by positional-state-store, but in this engine the write is done by the layer computation.
- ninfer [prefix-reuse] context-resource-manager: approximate — where it places an optional restore point shortens the prompt chunk that ends there, and a shorter chunk runs at another activation precision than the unsplit read; the type names this placement only at rounding. Own or through: the capture decision is this node's, the precision change is done by the layer computation of the shortened chunk, so it may be read as an effect through prompt reading
    evidence: capture_policy.cpp 8-29 chooses a capture position inside the chunk (begin, end] snapped to a semantic boundary; corrections for chunked-prefill and context-resource-manager: activation precision of AllowA4 projections follows the step's token count
- splash [memory-planning] streamed-parts-planner: rounding — deciding that a large part streams instead of staying resident switches prompt reading to grouped chunks of several sequences run layer by layer, which changes how the computation is cut (not a size, so the through-list's 'a size it sets, such as the prompt chunk' does not name it)
    evidence: prefill-runner groups up to four chunks run layer by layer when experts stream or K/V spills; the planner decides whether routed experts and the PLE table stream
- splash [memory-planning] streamed-parts-planner: defines — the per-request allowance and spill floors it sizes decide whether a request spills, and a spilled request's output is ended at the slower tier's quota
    evidence: planner sizes the KV allowance first and the floors of KV spill; kv-spill-controller (corrected to changes_output) ends a request at the quota bound
- splash [memory-planning] memory-plan: defines — the longest context one request may take is computed by the plan, and requests are refused or ended at that bound, so the plan decides where output stops; the through-list names cuts, approximations and step width but not the context bound
    evidence: memory-plan gives lane-admission the maximum context; 'context bound by model window, resident memory, or spill and disk'; prompt-builder returns ContextLengthError on overflow
- splash [model-loading] weight-image-loader: rounding — weights used only for proposals are reduced in precision at load, and the proposals decide where checked blocks begin and how many rows they hold
    evidence: draft quantized to af4g64 at load; greedy target output depends on rows per command through kernel tiles and split counts (kernel-selector), and verified rows for MoE follow draft confidence (verify-row-budget)
- splash [positional-state-store] draft-state: rounding — keeping only the inputs of derived per-position state and rebuilding it after a restore computes the proposer's state by another path (a prefill chunk instead of decode writes), which changes proposals and so the boundaries of checked blocks; under sampling it changes the draw (resampled). Partly own work (the decision what to keep), partly the proposer's computation: cannot fully separate
    evidence: cached states keep the context window, not the ring; the ring is rebuilt in the next prefill chunk after a restore (DFlashDraft.hpp:21-69, Runtime.cpp:363-371)
- splash [state-tiering] kv-spill-controller: rounding — moving a sequence's state to the slower tier switches how its prompt and history are computed (grouped chunks run layer by layer, history streamed one attention layer at a time), changing how the computation is cut; state-tiering has no affects_output_through
    evidence: prefill-runner groups chunks when K/V spills; spilled-kv-reader streams history per layer during prefill
- splash [step-scheduler] request-scheduler: rounding — the prompt cut is sized from measured wall time of past commands, so the same request can be cut differently from run to run; the through-list names the cut but not that it follows timing (named only for draft-policy)
    evidence: 'contended prefill cut rows from measured time with a floor'; 'sized while decode waits to a time bound measured from past commands'

## Relaxations

- strata [calibration] speed-calibration: A recorded result is used only where its validity key matches the model, machine and build. — The calibration record is applied at launch when the model name, context length and image setting equal the configuration's (launch-argument-resolver), so the model is identified by name, not by its files; a preset whose driver or tuning epoch changed is still applied, with a re-check offered.
- strata [layer-compute] output-head: An approximation that is in effect is stated with the run's settings. — On the pack path the activation is quantised to 8-bit q8_K before the vocabulary projection by default (src/core/layer.cpp:1425; avoided only by loading the head natively); no run-time statement of it is recorded, and the run manifest that lists tensor formats is off unless a file is named.
- ds4 [prefix-reuse] disk-kv-checkpoint-store: Stored state is reused only where the model, the weights' precision, the settings and the prefix match what it was made for. — Checkpoints are keyed by a hash of the rendered text prefix, not the token prefix; the token sequence of the restored state is not checked against how the new request's whole text would tokenize (the suffix is retokenized alone). The relaxed note names cross-precision reuse and missing settings, not a text key.
- hyperqwen [layer-compute] linear-gemm: An approximation that is in effect is stated with the run's settings. — The batch profile turns int8 activations on by default for the MLP layers (batch/start_qwen.sh:156 INT8_ACT=${INT8_ACT-int8}); the launcher exports the knob without printing it (launcher_common.sh:120-125). Whether vLLM itself logs the W4A8 path was not checked. The relaxed text describes a row-count default and a conversion permit, not a per-profile default chosen by layer name.
- splash [prefix-reuse] prefix-block-cache: Stored state is reused only where the model, the weights' precision, the settings and the prefix match what it was made for. — The persistent tier's namespace keys on model manifests, KV and state layouts and formats, and RoPE scaling (RuntimeResources.mm:540-584), and block keys on parent, tokens, images and salt, but neither includes the Neural Engine split (on by default, W8A8 for part of dense prefill FFN, its calibrated share, or a breaker trip). KV computed with the split is reused by a process run with --disable-ane or another share, and within a process across a breaker trip.
- splash [prefix-reuse] composite-state-cache: Stored state is reused only where the model, the weights' precision, the settings and the prefix match what it was made for. — Same key as the KV blocks: GDN states and draft windows computed from prefill that ran the reduced-precision Neural Engine split are restored where the split is off or at another share; state format is keyed (bf16 line in the namespace), the split is not.

## Inventory errors

- strata expert-cache.output_effect: recorded 'none; bit_exact when the GPU and CPU expert kernels round identically'; source shows 'Under the default route tail skip a missed expert is omitted only when not resident (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822), so what the cache holds changes output beyond rounding, as the correction records for adaptive-tier.'
- strata mtp-drafter.output_effect_when: recorded "bit_exact when the verifier's result for a token does not depend on which window it was verified in (and the arithmetic conditions hold); otherwise numeric"; source shows 'The default tail skip omits a missed expert only when every token of the verify window routes it at rank 7 or lower (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822, on when batch slots are off), so the drafts and the window width decide what is omitted for the accepted rows: approximate on the default solo CUDA path, not bit_exact or numeric.'
- strata dflash2-drafter.output_effect_when: recorded "bit_exact when the verifier's result for a token does not depend on which window it was verified in (and the arithmetic conditions hold); otherwise numeric"; source shows 'The default tail skip omits a missed expert only when every token of the verify window routes it at rank 7 or lower (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822, on when batch slots are off), so the drafts and the window width decide what is omitted for the accepted rows: approximate on the default solo CUDA path, not bit_exact or numeric.'
- strata lookup-drafter.output_effect_when: recorded "bit_exact when the verifier's result for a token does not depend on which window it was verified in (and the arithmetic conditions hold); otherwise numeric"; source shows 'The default tail skip omits a missed expert only when every token of the verify window routes it at rank 7 or lower (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822, on when batch slots are off), so the drafts and the window width decide what is omitted for the accepted rows: approximate on the default solo CUDA path, not bit_exact or numeric.'
- strata draft-policy.output_effect_when: recorded "bit_exact when the verifier's result for a token does not depend on which window it was verified in (and the arithmetic conditions hold); otherwise numeric"; source shows 'The default tail skip omits a missed expert only when every token of the verify window routes it at rank 7 or lower (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822, on when batch slots are off), so the drafts and the window width decide what is omitted for the accepted rows: approximate on the default solo CUDA path, not bit_exact or numeric.'
- strata draft-verifier.output_effect_when: recorded "bit_exact when the verifier's result for a token does not depend on which window it was verified in (and the arithmetic conditions hold); otherwise numeric"; source shows 'The default tail skip omits a missed expert only when every token of the verify window routes it at rank 7 or lower (src/core/expert_source.cpp:4963-4982; default set in src/program/generate.cpp:12776-12822, on when batch slots are off), so the drafts and the window width decide what is omitted for the accepted rows: approximate on the default solo CUDA path, not bit_exact or numeric.'
- ds4 weight-binder.output_effect: recorded 'none (and no decision about re-encoding)'; source shows 'ds4.c 3601-3646 (accelerator_cache_q8_tensors) and ds4_cuda.cu 5330-5378: on CUDA (not ROCm, not with DS4_CUDA_DIRECT_MODEL) 2-D Q8_0 tensors are cached as dequantized F16 or F32 device copies at load within a budget (ds4_cuda.cu 1562-1673); kernels then read the wider copy, so the effect is numeric and depends on available VRAM.'
- hyperqwen gptq-requantizer.when_things_go_wrong: recorded '[] (and must_never [])'; source shows 'The scripts write the variant directory in place with no temporary name: shard by save_file, then the index, then config.json last (drafter/gptq_lm_head.py:73-110, drafter/quant_dflash2.py:93-117); an interrupted run leaves a partial directory that is rejected at load only because config.json is written last or a truncated shard fails its header. The served copy is fetched prebuilt through temp file and rename (prepare/fetch_fast_variant.py:9,22-23). Each script also prints a round-trip error.'
- splash weight-image-loader.output_effect_when: recorded 'draft projections are quantized from BF16 at load, which changes draft proposals (not greedy target output)'; source shows 'Greedy target output depends in the last bits on rows per command (runtime/ops/KernelSelection.cpp:40-180 picks tile and split by rows and lanes) and, for MoE, on verified rows chosen from draft confidence (runtime/model/VerifyBudget.hpp); proposals decide accepted counts and so the next verify block. The draft quantization therefore can change greedy target output at rounding level.'

## Decisions not covered

- strata [configuration] launch-argument-resolver: devices the engine process may see and how they are enumerated
    missing (placement): which of the machine's devices the engine may use, and how they are identified to it
- ds4 [session-persistence] session-payload-serializer: under tensor parallelism, load only the tokens and recompute the state
    missing (policy): whether a restore loads the saved state or only the tokens and recomputes the state from them, per configuration
- ninfer [prefix-reuse] context-resource-manager: attention data parallelism: pick the attention-owner rank, balanced when peak load is within a bound of the minimum, then longest local prefix
    missing (placement): which device owns a sequence's attention and state when that work is divided between devices by sequence, and how load balance is weighed against where reusable state already lies

## Decisions covered loosely

- strata [configuration] run-config-generator: hand edits detected as differences from setup's last write and kept
    nearest: precedence: operator values, presets, measured values and defaults
- strata [configuration] launch-argument-resolver: one drafter per run; drafter options rewritten to match
    nearest: policy: how a known-bad combination is handled: refused, or one member replaced
- strata [draft-policy] draft-policy: window sizes a lookup window may use; a size whose graph finds no memory dropped
    nearest: sizing: limits on the round
- strata [draft-proposal] lookup-drafter: end positions kept per trigram
    nearest: threshold: how a lookup source matches earlier text, and how far back it searches
- strata [draft-verification] draft-verifier: conditions under which the exact gated rule is used, else the older rule with a warning
    nearest: policy: the acceptance rule under sampling
- strata [memory-planning] startup-memory-sizing: lowest value the reserve is lowered to
    nearest: failure: the order in which things are given up when memory is short, and when starting is refused
- strata [memory-planning] host-memory-admission: whether the engine may swap the arena for the file source on its own
    nearest: precedence: an operator's explicit size against the computed one
- strata [model-loading] model-file-reader: only one container version is read
    nearest: failure: what is done when a file is the wrong version, incomplete or of an unsupported shape
- strata [model-loading] expert-layout: native layout table when present, else canonical layout
    nearest: format: which stored encoding of a tensor is loaded when the files carry more than one
- strata [prefix-reuse] resume-decision: reuse of any kind needs a checkpoint capacity above zero
    nearest: sizing: how many are kept and where
- strata [row-source] ngram-reader: keep-alive reads in direct mode
    nearest: policy: warming the table in the background and when to stop
- strata [sequence-lifecycle] slot-scheduler: how often a prompt read gives way to a much shorter waiting one
    nearest: policy: the order in which waiting prompts are read, and whether several are read together
- strata [step-execution] window-loop: zero-doorbell or doorbell graph per window by residency
    nearest: policy: one step as a whole, or driven layer by layer
- ds4 [device-backend] gpu-backend: prefill workspace shared between sessions in server batch mode
    nearest: scratch and command buffers
- ds4 [expert-cache] routed-expert-cache: cache buffers locked in memory; a lock failure lowers the effective limit
    nearest: what is done when the cache cannot be allocated at its planned size (locking itself is named only in expert-source and model-loading)
- ds4 [memory-planning] memory-admission-guard: whether an explicitly raised OS wired-memory limit overrides the budget heuristics
    nearest: an operator's explicit size against the computed one (precedence)
- ds4 [residency-policy] expert-eviction-policy: use count incremented on every selection, misses included, not only on hits
    nearest: the replacement rule
- ds4 [residency-policy] expert-cache-preloader: cap on how many blocks are preloaded in automatic mode
    nearest: what the cache holds before any request
- ds4 [row-source] engram-prewarm: warm only when model, runtime, table and a reserve fit physical memory
    nearest: warming the table in the background and when to stop (names stopping, not the condition to start)
- ds4 [row-source] ngram-row-reader: prefetch only for chunks above a size and within a buffer cap
    nearest: prefetching rows for coming or drafted tokens
- ds4 [sampling] tool-call-sampling-mode: which tag sets count as structure
    nearest: whether settings change per position, for example greedy on structure and sampled on content
- hyperqwen [configuration] launch-profile-resolver: Drafter kind and number of draft tokens
    nearest: which settings that change output are on by default, and in which profile
- hyperqwen [configuration] launch-profile-resolver: Pin the pool by bytes or by utilisation; skip the pin under tensor parallelism
    nearest: rules that derive a setting's default from other settings and machine facts (the form in which a budget is expressed is not named)
- hyperqwen [configuration] launch-profile-resolver: Prefix caching on with align-mode recurrent state, and the snapshot retention interval
    nearest: which settings that change output are on by default, and in which profile
- hyperqwen [draft-proposal] mtp-drafter: Draft from the target's top-k/top-p support; optional draft temperature scale
    nearest: the set of tokens proposals are restricted to (a temperature applied to proposals is not named)
- hyperqwen [layer-compute] full-attention-compute: Sparse attention budget when the sparse mode is on
    nearest: any deliberate change to the model's arithmetic (the size of an approximation is not named)
- hyperqwen [model-conversion] draft-vocab-builder: Which extra scripts are appended to the derived vocabulary and under what row budget
    nearest: the data a derived piece is selected or fitted from, and what is eligible for it (forced inclusions and a reserved budget are not eligibility)
- hyperqwen [model-partitioning] tensor-parallel: Size the pool from utilisation rather than the single-card byte pin
    nearest: per-device budgets
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Flush a finished request's full block but discard a partial one
    nearest: when state held in a staging precision is converted to its stored format (what happens to staged state when its sequence ends is not named)
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Keep retired sinks resident; evict oldest first only when slots run dry
    nearest: which positions are kept at higher precision than the stored format (for how long, and the eviction order of such positions, is not named)
- hyperqwen [positional-state-store] kvarn-staging-quantizer: Draft passes after the first only allocate slots, never flush
    nearest: when state held in a staging precision is converted to its stored format (not converting state that may still be rejected is not named)
- hyperqwen [sampling] sampler: One top-k selection instead of a full sort when every request's top-k is small
    nearest: the kernel used for the sampling arithmetic, and how it changes with the number of rows (here it changes with the settings of the requests in the step)
- hyperqwen [state-tiering] kv-offload-tier: Which groups count as draft attention (only the drafter's window groups)
    nearest: which kinds of state the slower tier holds
- ninfer [configuration] configuration: defaults per model (prefill chunk by model and path)
    nearest: rules that derive a setting's default from other settings and machine facts (the served model is neither a setting nor a machine fact)
- ninfer [expert-dispatch] hybrid-moe-dispatch: large T (stream the whole layer) versus small T (split with the CPU) by a token-count threshold
    nearest: the share of misses fetched now against left to another device (the switch is by the step's token count, not by a share of misses)
- ninfer [media-preparation] media-preparer: cache capacity and live payload budget
    nearest: caching of prepared media and its key (no choice names a memory budget for prepared payloads held by caches and requests together)
- ninfer [memory-planning] startup-memory-planner: bounded correction of automatic capacity after an over-budget preparation; explicit capacity kept
    nearest: whether a failed allocation is retried smaller, and by how much (here nothing failed to allocate; a measured total exceeded the budget)
- ninfer [model-loading] shard-materializer: whether a slice can be expressed value-preservingly, else the format rejects it
    nearest: whether weights are re-encoded at load and how
- ninfer [prefix-reuse] context-resource-manager: cross-rank copy only when recompute cost was measured and it is cheaper
    nearest: which store is used when several hold a match
- ninfer [sequence-lifecycle] model-session: full permit before verify that covers the later commit peak
    nearest: a sequence's state allocated up front or grown on demand
- ninfer [step-execution] rank-program: where host handoffs split device work (grammar mask, CPU experts, final acceptance)
    nearest: cutting a step into parts so that work on two devices overlaps
- splash [draft-policy] verify-row-budget: refit interval, label window, decay, prior strength
    nearest: how fresh the signals it decides from must be (covers window and decay; refit interval and the prior's strength are not named)
- splash [expert-cache] expert-store: release one chunk, or all to floor under critical pressure
    nearest: which part is released or regrown first under memory pressure (names which part, not how much is released at each pressure level)
- splash [model-loading] weight-image-loader: quantize the draft at load rather than ship it quantized
    nearest: whether weights are re-encoded at load and how (names re-encoding, not where a precision reduction of proposal-only weights is done: offline or at every load)
- splash [output-constraint] thinking-budget: where in the 8 rows the end starts
    nearest: how it applies to proposed tokens that are not yet accepted (forcing replaces proposals at a chosen row rather than masking them)
- splash [output-interpretation] output-parser: hold text that may begin a stop string
    nearest: stop conditions and their order (the holding itself is the must rule, not a listed choice; how much is held and when it is released are not named)
- splash [residency-policy] slot-recycler: scans leave no ghosts and move no hits
    nearest: the replacement rule (does not name whether a one-pass bulk access is treated as a scan that leaves the use history untouched)
- splash [state-tiering] write-behind: minimum depth and delay before copying
    nearest: copying ahead of need (names that copies are made ahead, not what qualifies a restore point for a copy: its depth, its age, whether it was superseded)
- splash [telemetry] telemetry: log only transitions
    nearest: what is recorded by default and what on request (does not name recording state changes only rather than every sample)

