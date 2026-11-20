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

## Early timing bracket

Use `early-bracket` only after each scope has shut down under the early probe
protocol. Admit exactly one stock/candidate-on/stock sequence with one discarded
and one measured request at each prompt size per launch. For C5, the outer
strict A launches enclose A-matched/C5/A-matched. Report the inner candidate
comparison and the separate effect of stock runtime settings. C2 must name the
retained CPU-identity, all-CPU placement-policy or equivalent-placement control.

Bind actual scope command and binary receipts, source conditioning, prelaunch
quiet and request boundary checks, the pinned model receipt, prompt bytes,
resource windows and component markers. Reclaim-only max events are allowed.
Refuse safety stops, process contamination, mismatched flags or missing cells.
Preserve qualified measured timings when matched greedy outputs diverge and
mark them ineligible for candidate attribution. Cross-settings differences are
reported separately from matched parity. The report lists absolute endpoint
TTFT and decode values with observed drift and estimates no confidence interval.

For the held-out layer-27 placement functional lab, admit three capped launch
receipts in equivalent-stock, gate-unset, gate-enabled order. Check the pinned
plan and flags, exact named tensor readback, all other expert placements, gate
silence, aggregate CUDA0 model allocation and both greedy output hashes. Keep
one discarded request per prompt and arm for phase diagnosis only.

The native cache pilot compares all eight matched request positions of the two
30 GiB warm-up launches. Keep launch-to-ready and seed upload separate, and
keep the request positions descriptive. The full cache lab requires all six
ordered scopes, zero sampled residency in both external pack views before each
launch, three warmups per size, then five matched positions per size. Sum phase
counter deltas only within a single stable engine PID. Preserve host NVMe
counter deltas separately from process reads. Report range and residual trend
within each launch. A same-budget native-bank control isolates the treatment
more closely than either a plain stock engine or a different quantized pack.

The direct A-matched and fair Strata reference uses the same cold and
post-warmup admission for those two scopes. Resolve the unique Strata engine
PID inside its capped service scope and retain its phase counters independently
from the Python HTTP process. The direct iteration links back to the P1
reconnaissance and contains no candidate DO attribution.

The interim C3 60-GiB screening admits the completed A-matched, C3 and
fair Strata launches. It retains the combined bank-and-profile comparison
and defers same-budget stock attribution until that reference completes.
Strata's native engine prefill log and parsed file, page-cache, layer reuse
and worker-time counters remain separate from client-phase counters.

For each completed post-warmup arm, retain median and observed range of
sampled expert page residency and cgroup memory.stat file bytes immediately
before the five requests at each size. The former describes external inodes
in the host page cache. The latter describes file-backed charges to the
cgroup. The planner artifact names every sample receipt.

The full exploratory C3 screening also admits the owner-named iteration-2
CPU lane in its three authorized scopes when the observed PID, service
cgroup and affinity prove that it ran on CPUs 12–19. Preserve which source
conditioning, launch and request boundaries observed its processes. Keep
the affected comparisons exploratory. Strict timed P4, the prior warm-up
pilot, the direct A/S reference and the earlier 60-GiB screening retain
their separate quiet rules.
