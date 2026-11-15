# Native positive prefill chunk experiment

Change only `--prefill-chunk 256` to `512`, with `--dspark none` in both arms. Preserve full six experts, static cache, image, model, all environment and resource limits. This component supports 256/512/1024 for later separately frozen contracts. No engine source is changed.

`src/dsv41/ds4_main.cpp:2549` parses the flag. `ds4_model.cu:2724` enables the chunk path for a positive setting unless DS4_WINDOWS intervenes; `2789` selects an explicit value; `2792` allows DS4_CHUNK to override it; `2806` rounds to multiples of 16 and clamps ordinary values to at least 256. The component rejects override environment keys. Zero and 128 are deliberately excluded. Chunk buffers can reduce expert placement, so a prefill change can affect decode.

The separately versioned strata-benchmark-v2 contract freezes baseline256/candidate512, native protocol spec=0 in both arms, ARC quality64/main and train2/pilot, speed pp512/tg128 and ABBAABBA/main. Its primary rate is generated tokens divided by summed native prefill plus decode seconds. Exclude one warmup request per process. Preserve the v1 quality/resource/bootstrap gates. Draft counts must be zero; draft engagement is not required. Startup/tokenization/client overhead remain excluded.

Record effective startup chunk, prompt timing, decode timing, peak memory, expert placement and any file/copy counters. Reject incomplete evidence or quality regression, and preserve null results. A profile receipt proves a single treatment; runtime startup must still prove engagement. No automatic promotion follows a result.

The November 15 extension preserves a strictly validated opt-in `DS4_EXPERT_BUDGET_BYTES` while changing the chunk. It requires a source-qualified fixed-budget engine and native safe-budget/placement evidence. It does not widen historical benchmark contracts, submit a run, or infer that the supplied image supports the extension. Override keys remain rejected. A separately frozen pg4096/tg16 test can examine long prefill without confusing it with the existing pg512/tg128 score.

The coverage tool was added after the manual round exposed that all eight initial ARC prompts fit one256-token chunk. It predicts chunk counts from lengths only. A few-shot ARC test with disjoint train demonstrations exercises the actual changed chunk boundary; retain prompt construction, train/test IDs, tokenizer hashes and official-score=false.
