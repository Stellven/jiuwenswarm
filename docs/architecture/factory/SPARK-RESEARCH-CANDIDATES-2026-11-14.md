# Source-grounded candidates beyond native verified drafting

Research date: 2026-11-14. Local engine inspected at `ffa80d73133ea5c548aefe57889a16e8085a938f`. These are hypotheses and implementation proposals, not measured Spark gains. Paper benchmark results are not transferred to GB10, DeepSeek V4.1, IST-DAS 2.00bpw, or this engine.

## Hardware and baseline constraints

[NVIDIA's system overview](https://docs.nvidia.com/dgx/dgx-spark-porting-guide/latest/overview.html) describes shared CPU/GPU LPDDR5x, a hybrid ARM CPU and a 273 GB/s memory interface. UMA permits shared access, but an engine can still allocate staging buffers and issue copies. Therefore “offload bytes” must distinguish SSD reads, CPU memory traffic, explicit copies and GPU reads. A discrete-GPU PCIe latency argument alone cannot justify a Spark change.

[NVIDIA's optimization guide](https://docs.nvidia.com/dgx/dgx-spark-porting-guide/latest/optimization.html) recommends profiling, locality and reduced synchronization, and warns that cudaMemGetInfo excludes reclaimable page cache. Practical consequences: record OS available memory alongside CUDA free memory; preserve the host reserve; identify actual P/E-core placement before an affinity experiment. Do not change cache-drop, firmware, swap or host settings as part of a runtime knob experiment.

The existing verified-drafting CC uses native MTP; it is already a baseline mechanism. Generic “add prefetch,” “add expert cache” and “add speculation” proposals do not establish improvements beyond Strata: inspect the matching family implementation and prove a missing mechanism first. Historical llama.cpp router-prefetch/mmap interventions in the RSI fixtures are different engines and cannot establish Strata benefit.

## Candidate 1: positive prompt chunk 256 to 512 (implemented runtime CC)

Source: `src/dsv41/ds4_main.cpp:2549`, `ds4_model.cu:2724,2789,2792,2806,3554,3587`. A positive explicit chunk selects a layer-major prompt path. DS4_WINDOWS can suppress it, DS4_CHUNK overrides it, and ordinary values are rounded to multiples of 16 with minimum256. A requested128 is not a distinct treatment. Allocation can reduce the effective chunk or fall back to windowed execution; the startup line reports the resulting chunk.

Hypothesis: for pp512, one512-token chunk reduces repeated per-layer/expert work versus two256-token chunks. Counter-hypothesis: larger scratch allocation reduces expert placement or increases working-set cost, worsening decode enough to erase prefill benefit. Counters: exact effective chunk, native prefill/decode times, peak memory, experts resident/read in place, file read and copy counters where available. Falsify when effective chunks are equal, native prefill does not improve, or prefill-plus-decode rate fails its frozen gate. Compare actual native rates, not nominal chunk labels.

Implementation: `engine.strata_prefill_chunk.apply`, pure immutable profile transform; allowed256/512/1024. Actual v2 campaign freezes256/512, dspark none both arms and all existing full-six/static-cache obligations. Quality64/main and train2/pilot; speed512/128; first request discarded per process; ABBAABBA/main. Native protocol spec follows the profile. Primary rate is output tokens divided by native prefill plus decode time. Draft counters must remain zero. This is the first cheap experiment; runtime evidence and acceptance remain separate from implementation.

## Candidate 2: request-conditioned expert trace admission

[MoE-Infinity v3](https://arxiv.org/abs/2401.14361v3) selects sparse activation traces to guide cache replacement and prefetch. The useful question is whether per-request expert popularity predicts reuse better than the existing policy on the actual model and quantization.

Hypothesis: admit only high-confidence, deadline-feasible experts into a bounded warm tier, avoiding unconditional lookahead traffic. First implement trace replay, not GPU fetching: record expert IDs per layer, request boundaries, hits, bytes and deadline misses. Freeze training/calibration traces separately from held-out traces. Compare equal-byte LRU/LFU, prior-token, global popularity and request-conditioned policies. Report precision, demand recall, wasted bytes and counterfactual stall savings; an oracle is only an upper bound. Falsify if equal-budget replay gives no held-out improvement or predictor overhead exceeds saved stall time. Feasibility: medium; requires an audit of native DeepSeek store/cache integration, because generic `program/generate.cpp` lookahead is not proof that `dsv41` exposes that knob.

## Candidate 3: draft-aware bounded prefetch rather than wider unbounded speculation

[SP-MoE v2](https://arxiv.org/abs/2510.10302v2) combines speculative decoding with expert prefetch and a per-layer cutoff that limits fetching before verification. This motivates a scheduling hypothesis, not a claim that native MTP automatically provides compatible router predictions.

Hypothesis: use already-produced draft information to overlap only high-confidence target expert demand while keeping target routing and verification authoritative. Counters: accepted/offered tokens, target expert-set recall by layer, loaded bytes per accepted output token, wasted reads from rejected drafts, staging wait and GPU idle time. Controls: fixed draft block/confidence, equal cache bytes, fixed full-six target routing; compare no prefetch, demand-only and bounded predicted prefetch. Falsify if native draft/target correspondence is unavailable, deadline slack is insufficient, or extra traffic offsets overlap. Feasibility: medium/high; requires new engine instrumentation and must not substitute draft routing for target routing.

## Candidate 4: CPU/GPU execution choice calibrated for shared DRAM

[Fiddler v3](https://arxiv.org/abs/2402.07033v3) uses CPU/GPU orchestration and execution strategy selection instead of treating every missing expert as a mandatory GPU transfer. Its transferable idea is measuring the execution crossover.

Hypothesis: a small per-format/per-token-count cost model chooses CPU execution only when it reduces critical-path time after accounting for CPU/GPU DRAM contention. Counters: CPU expert microseconds, GPU expert microseconds, synchronized copy time, CPU worker busy time and OS scheduling, shared-memory bandwidth if available. Controls: same expert list/order, same quantization, all six experts, identical thread quota and allocations. Falsify when scheduling changes arithmetic beyond the admitted tolerance or GPU-only/direct shared-memory execution wins throughout the measured range. Feasibility: medium/high; ARM kernels must be measured, not inferred from x86 AVX tests. An opt-in async-thread count experiment is cheaper only after tracing its exact native source and proving it is on the exercised path.

## Candidate 5: earlier prediction without changing authoritative routing

[Pre-attention prediction](https://arxiv.org/abs/2511.10676v1) trains lightweight predictors on same-layer pre-attention activations. Its reported models differ from the deployed DeepSeek V4.1 pack. A future candidate can collect teacher routing and train an auxiliary predictor only to schedule reads. Require held-out routing recall, predictor latency, added memory, actual deadline slack and a demand fallback; preserve the model router's output. Reject if apparent accuracy depends on overlapping calibration/test requests or cannot pay for prediction.

[Pre-gated MoE](https://www.microsoft.com/en-us/research/uploads/prod/2024/05/isca24_pregated_moe_camera_ready.pdf) instead moves selection to the preceding block as an algorithm/system co-design. This changes model architecture/routing and requires model training/quality evaluation. It is not an inference-only byte-equivalent CC for the existing checkpoint. Keep it outside this runtime campaign.

## Evidence and decision rules

Each candidate needs an independently frozen contract and one changed mechanism. Profile receipts, replay results, synthetic tests and real engine runs are different evidence classes. Require effective engagement, complete raw artifacts, measured placement/memory and quality checks before speed interpretation. Run equal-workload A/A controls; paired ABBA limits order bias but four pairs remain a small sample. No paper-derived speedup, accepted replay or noisy pilot authorizes promotion. Measure the final stack directly instead of multiplying gains from separate interventions.
