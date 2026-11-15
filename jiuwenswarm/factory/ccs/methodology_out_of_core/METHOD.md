# Out-of-core workload and cache protocol

A model larger than physical memory cannot be wholly warmed at once. Declare a first-request-after-initialization phase and a fixed repeat phase. Neither means cold SSD. Restart the engine between cells, use fixed warmup/request counts, disable prefix reuse, and retain the same tokenizer, prompt, seed, output cap and full-expert policy.

Record native prefill/decode and end-to-end latency separately. Record phase physical reads, headroom, effective placement/cache/draft behavior, and collector overhead. No builds or agent processes should run during scored cells; use the host lab lease, not a promise in prose.

Do not drop global host caches, treat hardlinks as independent page cache, or attribute first/repeat differences to a code change. Counterbalance A/B order in independent blocks; diagnose cache carryover and report uncertainty. Traces explain behavior; they do not score.

Call `cache_protocol` with retained evidence IDs for a proposal. Host admission, experiment limits and immutable contract checks remain mandatory. The methodology cannot admit or launch a cell.
