# Verification method

Run these checks in order and retain the diff, source pin, workload identity,
commands and outputs with the task.

| Order | Stage | Check |
| --- | --- | --- |
| 1 | fixture | Run the capsule's unittest suite. Exercise a good diff, a missing INFO marker, a forbidden sampler edit, an inapplicable diff and a gate that enables by default. Run the helper checks on synthetic logs and responses. Replay the candidate's lease implementation on known bytes with repeated expert reads, multiple tensors sharing one lease, delayed last reader, two overlapping operations, pinned-full admission, eviction after release, allocation or lease failure, and partial submission. Compare to plain-copy bytes including padding, and assert the ledger peak and release order. |
| 2 | native CC execution | Call `verify` on the owned checkout and diff. Require a passing `git apply --check`, the verifier path allowlist, router and sampling protection, an added default-off gate, and added INFO marker signatures. Check the narrower work-order scope by inspection (including read-only model files), along with the lifecycle, data and accounting invariants. |
| 3 | compile | Review the verifier's best-effort `g++ -fsyntax-only` result for new sources and headers. Then compile the changed translation units under the configured engine build, including consumers of modified headers, and link a runnable binary. If standalone syntax needs generated or target-specific headers, retain its skipped result and use the configured compile as evidence. |
| 4 | runtime acceptance | Within each frozen configuration compare plain stock, patched gate unset and patched gate enabled via byte-identical greedy stdout. Run with `-lv 4 -lm mmap` and confirm the effective mmap mode. Use a repeat-demand workload that actually exercises the selected host weight copy. Require one first-use active line, one exit stats line, positive leases/reuses/avoided upload bytes, and peak bytes within the admitted cap. Exercise native `--moe-cache-mib` and non-mmap separately, holding each bypass configuration fixed between baseline and candidate. Confirm the inactive reason and zero capsule reuses. Exercise lease failure and confirm the plain copy and inactive transition. |
| 5 | hardware measurement | If authorized, measure stock versus engaged cache under the same frozen workload and placement, with the factory's paired method. Record elapsed time, stock-path upload bytes, staged copy traffic, counters, placement and memory conditions. Report null or negative outcomes as measured. |

Use the [CC v2 Host command](VALIDATION.md) for a receipt. The equivalent native stdin packet is
`{"capability":"verify","inputs":{"checkout":"/owned/llama.cpp","diff_path":"/owned/candidate.diff"}}`.
Relative patch paths resolve from the native process working directory. Omitting
`diff_path` checks staged, unstaged and nonignored untracked edits against HEAD.
The verifier expects adjacent added C++ declarations equivalent to
`const char * gate = std::getenv("LLAMA_EXPERT_CACHE");` and
`const bool enabled = gate != nullptr && std::strcmp(gate, "1") == 0;`.
Use `LLAMA_LOG_INFO` with each required literal prefix in added lines. For an
existing part include the final declarations and log calls in the candidate diff,
rather than relying on strings outside the diff. The static gate and marker scans
check source shape. Inspect control flow and use runtime acceptance to establish
their behavior. The syntax probe checks an isolated overlay of the patched files.

Any failed check makes verifier `done` false. A skipped syntax probe permits
static completion and supplies no compile evidence. A fixture pass establishes
fixture coverage. An apply pass establishes applicability. A configured compile
establishes compilation and linking. Use runtime acceptance for parity,
activation and observed fallback. Use hardware measurement for a speed claim.
Do not infer runtime engagement, byte parity, lease correctness or speed from a
fixture, native signature check or compile. Avoided upload bytes alone cannot
establish lower aggregate memory traffic or higher throughput.

## Gate-unset silence check

Inspect `verify` result `gate_unset_silence` and trace any inconclusive call
through the local code and its callers. Review first use, fallback and teardown for an early
stock return with no component work beyond one cached `getenv` check. In the
gate-unset arm at `-lv 4`, require the saved server log to pass:

```sh
python helpers/check_markers.py candidate-unset.server.log --name expert_weight_cache --expect-silent
```

Require all component marker lines to come from gate-set arms.

Review informational `high_churn_signatures` findings against the additive
alternatives in [SOURCE-MAP.md](SOURCE-MAP.md).

## Profile-driven Spark treatment

Follow [PROFILE-RESIDENCY.md](PROFILE-RESIDENCY.md) for a separately admitted residency comparison with reproducible controls. Retain the native verifier result and fixture acceptance before interpreting runtime timing.

## Report-led prefill hit admission

Follow [PREFILL-HITS.md](PREFILL-HITS.md) to verify GPU hits avoid original host payload reads and compare refill/copy amplification under matched admission.

Use [DIRECT-SEED.md](DIRECT-SEED.md) for the independent, report-driven native profile startup I/O treatment.

## AQBC seeding premise

Apply [the profiling patch](helpers/aqbc-profile-trace.patch) to the pinned AQBC source.
Use the profiling library with the pinned server and GGML libraries for the
authorized profiling load. Set `LLAMA_MOE_CACHE_TRACE` to an absolute writable
path. The profiling patch leaves the replacement policy and routed operands
unchanged. It flushes the header and each route record so the host can record
request boundaries. MCT1 only emits demand-slot records and cannot establish the
large-prefill premise.

MCT2 uses the native MCT1 allocation header following the four-byte magic
`MCT2`. Each little-endian record starts with four signed 32-bit integers
`layer, experts_per_token, count, projection`. Projection `-1` is a demand
update and has `count` ordered signed 32-bit expert IDs. A nonnegative
projection is the index of a read-only weight tensor in its group; the body has
`count` pairs of signed 32-bit expert ID and route frequency. A bulk read
neither fills slots nor ages the cache.

Pass `request` to `check_seeding_premise` with SHA-256-pinned `parent`,
`trace`, and `manifest` file references. The manifest format
`factory.muse-seeding-profile/1` includes `parent_sha256`, `trace_sha256`,
`profiling_library_sha256`, and ordered `requests`. Each request includes
`id`, `cell`, `cohort`, `trace_start`, and `trace_end` byte offsets. The
offsets partition all records after the header. Non-startup requests add
`prompt_sha256`, realized `prompt_n` and `generated_n`, and `cache_prompt`.
Separate native startup work into a leading `warmup` row with cell
`startup`. Held-out cells are `first-request`, `warm-512`, `warm-2048`, and
`follow-up`, all with prompt reuse enabled. Record any follow-up priming as
`warmup`. Collect independent `calibration` requests after the last held-out
request with prompt reuse disabled.

The verifier ranks only calibration transfers by their weight bytes. It leaves
one eighth of the admitted cache slots available for ordinary demand fill.
It replays the held-out records with the same cache geometry and replacement
policy for each arm, reports byte-weighted hit rates and estimated host upload
savings per cell, and records the profile's additional startup upload bytes.
The premise can pass its verification with `may_build: false`. A build
requires positive net held-out host upload savings and no first-request
regression in the paired replay. Timing, output identity, and memory
eligibility require the authorized target experiment.
