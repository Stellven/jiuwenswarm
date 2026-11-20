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
