# Spark P4 timing and page-cache protocol

Freeze the admitted arm list before the first measured launch. Use the strict A
flags for stock and any candidate that activates with those flags. Record the
cache settings chosen by native tuning for A+. Freeze the task-owned pre-run
Strata expert profile and run S read-only. A separately matched activation
profile can establish a candidate mechanism when strict A cannot activate it.

## Mirrored launches and repeat pairs

Run one server at a time under `bin/capped`, with a fresh result directory and
an exclusive quiet window. Retain an explicit `bin/quiet` preflight for each
scope. Record auth-free engine commands, binary/model identities, memory evidence
and readiness. Report actual kernel affinity/limits and monitor reclaim events.
On OOM, watchdog kill or unexpected termination, stop and preserve the receipt.

Use the same admitted arm order in the first pass and its reverse in the second.
For example, `A S A+ C1 C2 C2 C1 A+ S A` projects to ABBA for every comparison.
Start a new scoped process for both middle entries. After each server is ready,
discard four fixed warmup requests in order `512, 2048, 512, 2048`. Save all four
raw results with `--repeat 0 --discard` and distinct output directories. Every
request uses the approved prompt bytes, 32 greedy output tokens, seed 1 and a
disabled prompt cache.

Measure paired repeats 1 and 2 in each first-pass scope, 3, 4 and 5 in each
second-pass scope. For each repeat use `512, 2048` on odd indices and `2048, 512`
on even indices. Match by prompt size and repeat across arms. Keep the load and
warmup artifacts separate from request timing. `factory.spark_gap_analysis`
checks the mirrored order, warmups and matched repeats and reports 95% paired
bootstrap intervals conditional on the two launch windows. The intervals only
resample repeat pairs within windows. P1 contributes no observations to P4.

After starting the capped server and checking its readiness, run the window
client. `--arm` and `--port` must match the scope start receipt. For pass 2,
pass the same arm's completed pass-1 `p4-window/window.json` as `--first-window`.

```sh
python3 ops/spark/run_p4_window.py --scope "$SCOPE" --arm A --port 8082 \
  --launch-pass 1 --view llama --regions "$RUNS/source-regions.json" \
  --quiet-preflight "$PREFLIGHT"
```

The client writes `p4-window/window.json`, bench request/result/SSE artifacts,
before/after resource checks and adjacent page-residency receipts. It requires
exact token counts, no cache hits and unchanged content/reasoning hashes for
each prompt across both launches. It retains and fails a contaminated window
when a boundary check sees another model, build, test or Factory controller.
Boundary process checks do not prove the absence of transient work between
checks. Model load contributes to the in-window load average, which is retained
as context. The prelaunch receipt enforces the idle load threshold.

## External source-page cache

Build the region manifest once before the timed window from the retained GGUF
header parser and the Strata pack's `ds4.txt`/`tensors.txt` index. Use the actual
paths for the two engines. The llama view includes the converted Engram shard
symlink resolved to its real file. The Strata view includes the Engram table
and its small `engram.bin` index and excludes the inactive DSpark file. Device and
inode identify independent caches or aliases even where byte content matches.

```sh
python3 ops/spark/source_residency.py index \
  --llama-model "$MODEL" --converter "$CONVERTER" --strata-pack "$STRATA_PACK" \
  --out "$RUNS/source-regions.json"
```

Use identical stride/seed at every snapshot. Save `both` views before each
launch. At each completed warmup round, capture the current arm's view and
retain its scope accounting. Just before every measured request, sample the
same view after the previous request completes. Optional immediately after
each request snapshots show drift. Keep sampling and JSON writes outside the
client's TTFT timer.

```sh
python3 ops/spark/source_residency.py sample \
  --regions "$RUNS/source-regions.json" --view llama --scope-json "$SCOPE/scope.json" \
  --out "$SCOPE/before-repeat-1-512-residency.json"
```

The Linux `mincore` sampler uses read-only mmap and never reads tensor payload
pages. Its deterministic sample is weighted by source pages, by expert,
Engram and dense region. The cgroup `file`/`anon` entries are separate memory
accounting and can differ from the external inode page-cache fractions. Inode
residency does not measure selected-expert residency, physical I/O or GPU
allocation. The common warmups control request exposure. Retain any remaining
imbalance by arm and prompt in the report and qualify the comparisons where
residency differs. Report other matched counters separately from TTFT.

Before each P4 server launch, run `source_residency.py cold-start --regions SOURCE_REGIONS --out NEW_RECEIPT` under the same protocol for both engines. This acquires the free GPU lock, verifies the quiet preflight, advises eviction of clean pages only on the indexed source files, and samples both packs before and after. Preserve the actual residual fractions. Then take the launch quiet receipt and start the server. Carry out both warmup rounds and the pre-request sampling as above. Keep file-conditioning time outside server load and TTFT measurements.

## Early owner timing brackets

The early pilot uses one discarded 512/2048 round then one measured 512/2048
round in each scope. Pass completed stock, candidate-on and stock scopes in
their actual order. For C5 pass strict A, A-matched, C5-on, A-matched and strict
A. The native post-lab report records all endpoints and controls. The pilot
does not enter the mirrored P4 estimate or produce a confidence interval.

```sh
python3 ops/spark/report_early_bracket.py C5 "$A0" "$MATCHED0" "$C5" "$MATCHED1" "$A1" \
  --products "$REVISED_BUILD_INVENTORY" --source-products "$REVISED_SOURCE_INDEX" \
  --functional-off "$C5_OFF_FUNCTIONAL" --functional-on "$C5_ON_FUNCTIONAL"
```

Use the build inventory passed to the probes. The source index uses the
`spark-source-products.json` field structure and identifies the exact factory
task, source decision, verifier, diff and commit. C2 also requires
`--placement-policy` and accepts a pinned `--placement-controls` override.
The publisher checks controls, seals and runs the analysis and verifier,
attaches the report to the selected source task, and prints the verified
report identity for the successor planner. Its accepted controls are the
`probe_candidate.py` early profiles. The native A+ budget comparison uses its
own separately admitted experiment and report.
