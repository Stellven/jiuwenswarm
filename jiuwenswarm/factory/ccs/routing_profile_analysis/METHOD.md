# Expert routing coverage and payload cost

Use snapshots of the same Strata profile taken before and after an isolated workload. Supply the matching pack's tensor index and the main model dimensions from its `ds4.txt`. Stage all three inputs as immutable artifacts. The capability records each SHA-256 in the report. Keep the engine, pack and workload provenance with the report.

1. Decode the snapshots as little-endian uint32 counts in layer-major order. Check the shape and use the main layers. Up to eight complete trailing drafter rows are allowed.
2. Rank each layer by the before count, breaking ties by ascending expert ID, as Strata does for profile-based placement. For each requested size, select that many experts per layer.
3. Subtract the before counts from the after counts. Reject a counter reset, rollover or empty observation. Pool counts across the main layers. Divide the selected count delta by the total count delta.
4. Sum the indexed `w1`, `w2` and `w3` bytes for each selected expert. Reject missing, duplicate or out-of-range tensor entries. Use the indexed payload, including quantized data, as the residency sizing input.
5. Invoke `verify` with the same inputs and the saved report. The verifier recomputes the report and checks every field. The synthetic tests check snapshot separation, ties, byte sums, incomplete indexes, and count decreases.

The result's ranked expert IDs can inform placement and cache builder capsules. Establish layer/expert identity for the target conversion before using the IDs, and measure admission and activation with the target engine. The byte calculation covers stored tensor payload. Actual device allocation can also include alignment, padding, scratch space and KV. Profile counters combine prompt and generation and carry no access order or transfer timing.

## Compare against a recorder trace

Use a trace retained after shutdown and the verified rank report as separate pinned artifacts. Document how layer and expert IDs correspond between the model packs.

1. Require each event to have a unique layer and microbatch key. Split row selections according to the recorded phase. Mixed dispatches need per-row phase tags. Keep unknown rows visible.
2. For each phase and tier, report coverage over all observed expert selections, including repeats. Within each dispatch and phase, also count each selected expert once. The latter denominator measures distinct layer/microbatch/expert combinations in each phase. A mixed dispatch can contribute the same expert to more than one phase.
3. Keep submitted copy bytes at dispatch granularity. Report known bytes and the number of events with unknown bytes for each dispatch phase. Count mixed-phase copy bytes separately because the recorder supplies no per-row split.
4. Reconcile the recorder's final counts with retained events and known submitted bytes. Preserve accounted loss, empty captures and missing summaries. Denote phase fractions with no denominator as null.
5. Call `verify_transfer` with the same artifacts and saved report. The synthetic tests cover mixed and unknown phases, repeat selections, missing summaries, loss and inconsistent receipts.

The report summarizes observed recorder events. A loss-free recorder summary does not substitute for an independent dispatch manifest. Use a matched workload to measure latency and controller activation before attributing speedup to the rank set.
