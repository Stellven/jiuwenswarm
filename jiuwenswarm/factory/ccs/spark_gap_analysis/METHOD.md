# Spark TTFT and gap analysis

Run `analyze` after the lab has saved immutable request, result, prompt manifest,
load-ready and capped scope receipts. The caller resolves the artifact IDs in
the task store and supplies their verified payloads and SHA256 values. The CC
executes a local calculation and returns the summary and contributing artifact
identities. `verify` recomputes the full result from those same inputs and checks
exact equality. Neither operation launches models or decides which arm to ship.

Use `p1-reconnaissance` for exploratory batches with unknown or unmatched
conditions. Preserve exclusions and show medians, ranges and output hashes.
Use `p4-abba` only with two mirrored launch passes under the lab's quiet
preflight. Independent scopes have verified cgroup controls, sequential
nonoverlapping lifetimes and a normal stop. Each launch discards two matched
512/2048 warmup rounds. The first pass measures repeats 1 and 2 and the second 3–5.
Both arms use the same alternating prompt order by repeat. The CC validates
order and matched requests, including actual prompt and output token counts,
prompt SHA256, seed, temperature and zero prompt cache reuse.

An arm's inverse-TTFT ratio is the control median divided by the arm median.
Gap closure is `(A − arm) / (A − S)`. It is undefined when A matches or beats S.
For P4, the 95% percentile interval enumerates all 108 paired bootstrap draws,
resampling repeat labels within the two launch passes. Arms share each draw.
It is conditional on those launch windows and excludes between-launch
uncertainty. If any draw lacks a positive A–S gap, omit the gap interval.

Report client TTFT, internal prefill duration and decode rate separately.
Load time is separately recorded per scope. Do not add phases across clocks,
infer phase causality from their differences or assign a CC a causal effect
without a matched gated arm with parity and activation evidence. Strata's
ordinary stream counters can be attached from `factory.deep_profile` scope
analysis. Aggregate worker, DMA and staging intervals can overlap.
