# Exact reuse and explicit storage accounting

`prefix(spec)` takes `identity` with nonempty string fingerprints `model`, `tokenizer`, `adapter`, `position`, `dtype`, `tenant`; `tokens` as integer token IDs; and `entries` containing the same identity/tokens structure. Optional `invalidated_models` denies entire model fingerprints. Return the longest contiguous exact prefix and uncached suffix. Fingerprints include weight revision, tokenizer/template revision, adapter weights, position/rope configuration, precision/backend layout and tenant. Update a fingerprint on mutation. Prefix state cannot be reused after a different preceding context, from arbitrary matching text fragments, or merely matching tokenizer names.

`allocator(spec)` takes integer `capacity`, `block_tokens`, and finite `operations`: create(owner,tokens), share(source,target), append(owner,token), release(owner), evict(page). Each owner owns one reference per mapped page. Sharing increments references; appending to a shared partial page allocates a private copy before decrementing the old reference. Appending to a full page allocates a new page. Allocation failure preserves current sequences. Release frees at zero references. Eviction rejects every referenced page, including an active request. This strict reference does not retain an unowned warm LRU: add explicit cache ownership/leases before adapting a retained radix cache. Tokens stand in for KV payload; no tensor kernels are implemented.

`estimate(spec)` requires layout `mha` with layers,tokens,bits,kv_heads,head_dim, or layout `mla` with layers,tokens,bits,latent_dim,rope_dim; optional batch,group_size,scale_bytes. MHA/GQA stores K and V per KV head; compressed MLA here stores one latent plus positional key. Verify the actual backend layout: expanded MLA, DeepSeek v4 compressed/windowed/indexer state, padding and quantization layouts may differ and require another formula. Never substitute a generic two-KV-head MHA estimate for MLA. Quantized estimates include group scale bytes and are explicitly approximate; they grant no admission or exact quality claim.

GB10 has unified memory: count its shared pool once. Use operator-supplied actual capacity (including a 64 GB target if configured), measured residency, OS/model/workspace allocations and reserve; do not add CPU RAM to GPU VRAM. ARM64, CUDA capability and model-specific DeepSeek v4.1 support remain unverified. Evaluate exact token equality separately from speed, hit rate and resident bytes. Compare cold/warm shared-prefix and no-prefix workloads, release/COW pressure, tenant isolation and changed revision invalidation. Retain actual runtime traces before a performance or engagement claim.

## Factory-stage CPU fixture

Use a public sliding-window GGUF under 1 GB on a caller-supplied CPU host. Use the
same executable and model in both runs. Start one CPU-only server at a time
after local admission. Disable device offload and run stock flags first, then
add `--swa-full --ctx-checkpoints 32`. In each run enable `cache_prompt` and send
the same two tokenized questions over a shared document of about 1.5 attention
windows. Keep separate startup and request logs.

`verify_cpu_fixture(evidence)` takes `model` with `bytes`, `sha256` and
`window_tokens`, `executable_sha256`, two `request_tokens` lists and
`configurations.stock` and `configurations.configured`. In both configurations
include `model_sha256`, `executable_sha256`, `extra_args`, `cache_prompt`,
`startup_log` and two `request_logs` slices. This CC verifier checks CPU
placement, the effective SWA mode and the first cached-token count in each
request. The target lab evaluates performance after delivery.

In this run, the Spark wrapper `scripts/factory/prefix_reuse_cpu_fixture.py`
used the delivered binary on a 253 MB Gemma 3 fixture. Both configurations
reused all 769 shared tokens of the 788-token follow-up with `cache_prompt`
enabled. Stock already reported a maximum of 32 context checkpoints. The
configured log additionally confirmed full-size SWA. The fixture measured
identical reuse with both flag sets.

## Muse Run 2 prefix reuse image

`verify_pins` reads the frozen AQB lab receipts, image check, prefill plan,
packed-model manifest, and the retained Phase 0 and Phase 0b evidence. Pack
verification uses the recorded manifest SHA-256, each shard's size and GGUF
magic. It reads no tensor payloads. `plan` records the placement refusal,
ties prefix reuse to the first cache count for the follow-up request, and
records the Phase 0b quiet exclusions separately from engagement.

The plan carries forward AQB's effective launch configuration and adds
`--swa-full --ctx-checkpoints 32` and request `cache_prompt=true`. On GB10,
the device budget counts the recorded model, KV, expert cache, compute and
host compute allocations once. The capped runner separately enforces the
96 GiB cgroup cap, zero swap, and live fit margin.

Pass the plan's `build_request` to `factory.builder.submit` from the graph's
`build_image` node. After the durable attempt succeeds, pass the exact Builder
`build-record` artifact and prefix plan to `verify_factory_stage`. The checker
verifies the unchanged root filesystem, executable and pack, and compares the
sealed image launch configuration against the plan. Lab delivery requires this
check. Runtime evidence determines release.
