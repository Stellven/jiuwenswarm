# Expert-streaming evidence method

Separate load, prompt and decode before attributing cost. Decode is printed
`eval_ms_per_token`; fill stats provide distinct prompt_* and decode_* fields.
Whole-run copy/IO time is not automatically a decode bottleneck. Counters with
no phase split cannot silently be described as decode counters.

These claims are different and require different evidence:

- Predicted right: hits, actual and recall_at_k describe routing recall.
- Bytes ready before demand: readiness counters split predicted and unpredicted
  selected bytes, when the readiness component is present. hit_done is IO job
  state, not a residency probe; resident-at-predict is not credited to prediction.
- Fewer faults/bytes: per-phase fault counters and bytes read need their own
  comparison. pread can replace faults without reducing IO; duplicate and wasted
  reads matter. Missing blocks are not_measured, never zero.
- Lower decode ms/token: only the untraced contract-bound ABBA gate establishes
  this. Neither recall, readiness, lower faults nor whole-run copy time implies it.

Traced nsys and DIAG=1 runs explain mechanisms; they perturb timing. Score
untraced ABBA. Read engagement per arm/run and preserve raw stderr artifacts.
The tool reports decode-byte and decode-wait rates only with an actual decode
token denominator (readiness or printed eval tokens), not layer call counts.

## Acceptance by module

Performance components (expert_fill, expert_pregate, mmap_advice,
router_prefetch, later inflight_join) require gate improved, complete valid
measurements, passing engagement and byte-identical correctness.
Observability components (thread_names, later expert_readiness) require every
candidate engagement check to pass, correctness pass and candidate overhead
`1/ratio - 1 <= max(overhead_bound, gate threshold)` where ratio=A/B ms/token.
thread_names has overhead_bound=0.03; no speedup is required and never claim a
speed gain from names. Missing signal capture is invalid, not rejection evidence.
Prerequisite source may stay dormant only per AB.md step 9; it is not an enabled
performance win. Cite acceptance.verdict=accept for keep_component.

A failed/null idea remains useful knowledge. Preserve all raw evidence and
negative results. A change of scoring rules requires a new contract id and fresh
reference, never relabeling old results. Do not multiply successive ratios:
final speed claims require direct bare-vs-final ABBA if budget allows; otherwise
state that the final comparison is not measured.

## Page-cache state is a confound

The model file (20.8 GiB) is far larger than RAM, so how much of it is cached
when a run starts changes decode speed a lot (a run starting at 0% resident
measured 1290 ms/token where warm ABBA chains measured about 711; J-XS2-smoke vs
J-OM13). Read `page_cache.start.json` for every run, compare start residency
across arms, and state the protocol (carryover, cold, warm) with any claim. A
comparison across different protocols, or with very different start residency,
is not a valid speed comparison.
